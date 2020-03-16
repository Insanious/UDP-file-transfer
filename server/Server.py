#!/usr/bin/env python


import socket
import time
import logging

from utilities.utilities import *

class Server:
	PACKET_SIZE = 1024
	SERVER_PORT = 80
	CHUNK_SIZE = 2048
	MAX_TIME_BETWEEN_PACKETS = 0.01
	START_SEQUENCE_NUMBER = 100000
	SERVER_DONE = "SERVER_DONE"
	META = "META"
	CHUNK = "CHUNK"


	def __init__(self):
		self.logger = logging.getLogger(__name__)

		self.logger.info(f"creating server socket on port {self.SERVER_PORT}")
		self.socket = create_server_socket(self.SERVER_PORT)
		self.client_address = None


	def receive_all_chunks(self):
		chunks = []
		packets = []
		new_packets = []
		remaining_sequence_nrs = []
		first_sequence_nr = file_size = nr_of_packets = last_packet_time = nr_of_chunks = 0
		file_name = ""

		file_meta, client_address = self.receive_file_meta()
		self.client_address = client_address
		file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks = handle_meta_packet(file_meta)

		chunk_sequence_nrs = generate_chunk_sequence_nrs(self.START_SEQUENCE_NUMBER, self.CHUNK_SIZE, nr_of_chunks)

		self.logger.info("sending META to client")
		self.reply_message(self.META) # send META to client, making the client send all chunks

		for sequence_nr in chunk_sequence_nrs:
			chunks.append(self.receive_chunk(sequence_nr, remaining_sequence_nrs))

		for chunk in chunks: # store all packets in a 1d list
			for packet in chunk[1:]: # remove chunk-meta packet from the data packets
				packets.append(packet[7:]) # remove sequence nr and delim from data packet

		self.logger.info(f"all {len(packets)} packets received")

		return file_name, packets


	def receive_chunk(self, chunk_sequence_nr, remaining_sequence_nrs):
		chunk = []
		new_packets = []
		remaining_nrs_in_chunk = []
		first_packet_received = False
		last_packet_time = 0

		while True:
			try:
				if first_packet_received and time.clock() - last_packet_time > self.MAX_TIME_BETWEEN_PACKETS: # artificial timeout, reply lost packets
					chunk, remaining_nrs_in_chunk = self.artificial_timeout(chunk, chunk_sequence_nr, new_packets, remaining_nrs_in_chunk)
					new_packets = []
					first_packet_received = False
					if self.reply_lost_packets(remaining_nrs_in_chunk):
						self.logger.info(f"all packets received in chunk {int((chunk_sequence_nr - self.START_SEQUENCE_NUMBER - 1) / self.CHUNK_SIZE)}")
						break

				packet, client_address = self.socket.recvfrom(self.PACKET_SIZE)

			except socket.error as e:
				if handle_socket_errors(e.args[0]):
					continue

			else:
				packet = packet.decode()
				new_packets.append(packet)

				if not first_packet_received:
					first_packet_received = True

					split_packet = packet.split(";")
					incoming_sequence_nr = int(split_packet[0])
					if incoming_sequence_nr == chunk_sequence_nr: # meta packet
						self.logger.info("chunk meta packet received")

						total_packets = int(split_packet[1])
						remaining_nrs_in_chunk = calculate_remaining_chunk_sequence_nrs(chunk_sequence_nr, total_packets)
						#self.logger.info(f"remaining packets in chunk:{len(remaining_nrs_in_chunk)}")

						self.logger.info("sending CHUNK to client")
						self.reply_message(self.CHUNK)

				last_packet_time = time.clock()

		return chunk


	def artificial_timeout(self, chunk, chunk_sequence_nr, new_packets, remaining_sequence_nrs):
		chunk, remaining_sequence_nrs = update_packets(chunk, new_packets, remaining_sequence_nrs)

		if len(remaining_sequence_nrs) != 0: # print information if there were lost packets
			padding = 7
			information = "chunk: " + str(int((chunk_sequence_nr - self.START_SEQUENCE_NUMBER - 1) / self.CHUNK_SIZE)).ljust(padding)
			information += "new: " + str(len(new_packets)).ljust(padding)
			information += "remaining in chunk: " + str(len(remaining_sequence_nrs)).ljust(padding)
			information += "total: " + str(len(chunk)).ljust(padding)
			self.logger.info(information)

		return chunk, remaining_sequence_nrs


	def reply_lost_packets(self, lost_packets):
		if len(lost_packets) == 0:
			self.reply_message(self.SERVER_DONE)
			return True # return True because there are no lost packets to be received

		packets = []
		remaining_nrs = len(lost_packets)
		sequence_nrs_per_packet = self.PACKET_SIZE // 7 # 7 for len(seq_nr) + 1 for delimeter
		sequence_nrs_in_packet = sequence_nrs_per_packet
		packet_counter = 0

		while remaining_nrs > 0:
			packet = ""

			if remaining_nrs < sequence_nrs_per_packet: # reduce loop iterations for the last iteration
				sequence_nrs_in_packet = remaining_nrs
			remaining_nrs -= sequence_nrs_in_packet # remove the number of sequence nrs left that we need to iterate through

			for i in range(0, sequence_nrs_in_packet): # create packet with sequence nrs
				packet += str(lost_packets[packet_counter]) + ";"
				packet_counter += 1

			packets.append(packet)

		self.send_all(packets)

		return False # return False because there are still lost packets to be received


	def send_all(self, packets):
		for packet in packets:
			self.socket.sendto(packet.encode(), self.client_address)


	def receive_file_meta(self):
		self.logger.info("trying to receive file meta packet...")

		while True:
			try:
				packet, client_address = self.socket.recvfrom(self.PACKET_SIZE)

			except socket.error as e:
				if handle_socket_errors(e.args[0]):
					continue

			else:
				packet = packet.decode()
				incoming_sequence_nr = get_sequence_nr(packet)
				if incoming_sequence_nr == self.START_SEQUENCE_NUMBER: # meta packet
					self.logger.info("file meta packet received")

					return packet, client_address



	def reply_message(self, message):
		self.socket.sendto(message.encode(), self.client_address)
