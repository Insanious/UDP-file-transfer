#!/usr/bin/env python
# coding=utf-8


import sys
import os


class File_Packager:
	PACKET_SIZE = 1024
	CHUNK_SIZE = 2048
	START_SEQUENCE_NUMBER = 100000

	def __init__(self, file_name):
		self.file_name = file_name


	def create_file_meta_packet(self, nr_of_chunks, nr_of_packets):
		size = os.stat(self.file_name).st_size # exists if not zero
		if (size == 0):
			print("invalid file size")
			sys.exit(0)

		meta = str(self.START_SEQUENCE_NUMBER) + ";"
		meta += str(size) + ";"
		meta += self.file_name + ";"
		meta += str(nr_of_packets) + ";"
		meta += str(nr_of_chunks)

		return meta


	def create_chunk_meta_packet(self, sequence_nr, remaining_packets):
		meta = str(sequence_nr) + ";"
		meta += (str(self.CHUNK_SIZE) if (int(remaining_packets // self.CHUNK_SIZE) > 0) else str(remaining_packets))

		return meta


	def file_to_chunks(self):
		chunks = []
		packet_counter = 0
		chunk_nr = -1 # because it gets incremented at first iteration

		sequence_nr = self.START_SEQUENCE_NUMBER

		with open(self.file_name, "r") as file:
			while True:
				if packet_counter % self.CHUNK_SIZE == 0:
					chunks.append([])
					chunk_nr += 1
					sequence_nr += 1
					packet_counter += 1
					chunk_seq_nr = sequence_nr

				sequence_nr += 1
				data = file.read(self.PACKET_SIZE - len(str(sequence_nr)) - 1) # -1 to account for the delimeter
				if not data:
					chunks[chunk_nr].insert(0, self.create_chunk_meta_packet(chunk_seq_nr, len(chunks[chunk_nr]) + 1)) # +1 to account for chunk-meta
					break

				data = str(sequence_nr) + ";" + data
				chunks[chunk_nr].append(data)
				packet_counter += 1

				if packet_counter % self.CHUNK_SIZE == 0: # insert chunk-meta after chunk has been filled
					chunks[chunk_nr].insert(0, self.create_chunk_meta_packet(chunk_seq_nr, len(chunks[chunk_nr]) + 1)) # +1 to account for chunk-meta

		meta_packet = self.create_file_meta_packet(len(chunks), packet_counter)

		return meta_packet, chunks
