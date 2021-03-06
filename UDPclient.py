#!/usr/bin/env python
# coding=utf-8

# A client that sends a file to a server using UDP-protocol #


import socket
import time
import errno
import sys
import os
import time
import math
import itertools


META_RESEND_TIME = 0.5
PACKET_SIZE = 1024
SERVER_PORT = 80
CHUNK_SIZE = 2048
MAX_TIME_BETWEEN_PACKETS = 0.02
START_SEQUENCE_NUMBER = 100000
SERVER_DONE = "SERVER_DONE"
META = "META"
CHUNK = "CHUNK"


def format_lost_packets(lost_packets):
	sequence_nrs = []

	for packet in lost_packets:
		splitted = packet.split(";")
		splitted = splitted[:-1]
		for sequence_nr in splitted:
			sequence_nrs.append(int(sequence_nr))

	return sequence_nrs


def send_meta_and_listen(client_socket, server_ip, meta_packet):
	while True:
		client_socket.sendto(meta_packet.encode(),(server_ip, SERVER_PORT)) # Send meta-packet
		meta_sent_time = time.clock()

		while True:
			if time.clock() - meta_sent_time > META_RESEND_TIME: # resend meta
				return False
			try:
				response, server_address = client_socket.recvfrom(PACKET_SIZE)
			except socket.error as e:
				if handle_socket_errors(e.args[0]):
					continue
			else:
				response = response.decode()
				if response == META or response == CHUNK:
					return True


def create_file_meta_packet(file_name, nr_of_chunks, nr_of_packets):
	size = os.stat(file_name).st_size # exists if not zero
	if (size == 0):
		print("invalid file size")
		sys.exit(0)

	sequence_nr = START_SEQUENCE_NUMBER

	meta = str(sequence_nr) + ";"
	meta += str(size) + ";"
	meta += file_name + ";"
	meta += str(nr_of_packets) + ";"
	meta += str(nr_of_chunks)
	return meta


def create_chunk_meta_packet(sequence_nr, remaining_packets):
	meta = str(sequence_nr) + ";"
	meta += (str(CHUNK_SIZE) if (int(remaining_packets // CHUNK_SIZE) > 0) else str(remaining_packets))

	return meta


def file_to_chunks(file_name):
	chunks = []
	packet_counter = 0
	chunk_nr = -1 # because it gets incremented at first iteration

	sequence_nr = START_SEQUENCE_NUMBER

	with open(file_name, "r") as file:
		while True:
			if packet_counter % CHUNK_SIZE == 0:
				chunks.append([])
				chunk_nr += 1
				sequence_nr += 1
				packet_counter += 1
				chunk_seq_nr = sequence_nr


			sequence_nr += 1
			data = file.read(PACKET_SIZE - len(str(sequence_nr)) - 1) # -1 to account for the delimeter
			if not data:
				chunks[chunk_nr].insert(0, create_chunk_meta_packet(chunk_seq_nr, len(chunks[chunk_nr]) + 1)) # +1 to account for chunk-meta
				break

			data = str(sequence_nr) + ";" + data
			chunks[chunk_nr].append(data)
			packet_counter += 1

			if packet_counter % CHUNK_SIZE == 0: # insert chunk-meta after chunk has been filled
				chunks[chunk_nr].insert(0, create_chunk_meta_packet(chunk_seq_nr, len(chunks[chunk_nr]) + 1)) # +1 to account for chunk-meta

	meta_packet = create_file_meta_packet(file_name, len(chunks), packet_counter)

	return meta_packet, chunks


def send_all_chunks(client_socket, server_ip, meta_packet, chunks):
	total_lost_packets = 0

	packets = []
	packets.append(meta_packet)
	for chunk in chunks: # get packets to 1d array
		for packet in chunk:
			#print(packet.split(";")[0])
			packets.append(packet)

	while True:
		if send_meta_and_listen(client_socket, server_ip, meta_packet): # send file meta
			break
	print("-META SUCCESS")

	for chunk in chunks: # send all chunks
		nr_of_lost_packets_in_chunk = 0
		nr_of_packets = len(chunk) # -1 to remove chunk meta

		while True: # send chunk meta
			if send_meta_and_listen(client_socket, server_ip, chunk[0]):
				chunk_nr = (int(chunk[0].split(";")[0]) - START_SEQUENCE_NUMBER + 1) / CHUNK_SIZE
				break

		print("-SENDING CHUNK " + str(int(chunk_nr)))
		for i in range(1, nr_of_packets): # send all packets, start at 1 because the first packet has already been sent (meta-chunk)
			client_socket.sendto(chunk[i].encode(), (server_ip, SERVER_PORT))

		nr_of_lost_packets = listen_and_send_lost_packets(client_socket, server_ip, packets)
		while nr_of_lost_packets != 0: # resend while there are any lost packets
			nr_of_lost_packets_in_chunk += nr_of_lost_packets
			nr_of_lost_packets = listen_and_send_lost_packets(client_socket, server_ip, packets)

		total_lost_packets += nr_of_lost_packets_in_chunk

	count = 0
	for chunk in chunks:
		count += len(chunk) - 1

	print("All chunks sent with a total of " + str(total_lost_packets) + " lost packets out of " + str(count) + "!")


def listen_and_send_lost_packets(client_socket, server_ip, packets):
	lost_packets = []
	lost_sequence_nrs = listen_for_lost_packets(client_socket)
	nr_of_lost_packets = len(lost_sequence_nrs)

	if nr_of_lost_packets == 0: # happens when server sends SERVER_DONE
		return 0

	for sequence_nr in lost_sequence_nrs:
		lost_packets.append(packets[int(sequence_nr)-START_SEQUENCE_NUMBER]) # packet_index = seq - start_seq

	send_all(client_socket, server_ip, lost_packets)

	return nr_of_lost_packets


def send_all(client_socket, server_ip, packets):
	for packet in packets:
		client_socket.sendto(packet.encode(),(server_ip, SERVER_PORT))


def handle_socket_errors(error):
	if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
		return True
	else:
		print(error)
		sys.exit(1)


def listen_for_lost_packets(client_socket):
	lost_sequence_nrs = []
	incoming_packets = False
	last_packet_time = 0

	while True:
		try:
			if incoming_packets and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # too long time between packets
				return format_lost_packets(lost_sequence_nrs)

			packet, server_address = client_socket.recvfrom(PACKET_SIZE)

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()

			if not incoming_packets: # first packet
				incoming_packets = True

			if packet == SERVER_DONE:
				return []

			lost_sequence_nrs.append(packet)
			last_packet_time = time.clock()


def create_socket():
	client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	client_socket.setblocking(False)
	return client_socket


def extract_arguments():
	if len(sys.argv) != 3: # sys.argv=[python_file(UDPclient.py), file_name, server_ip]
		print("invalid arguments")
		sys.exit(0)

	file_name = sys.argv[1]
	server_ip = sys.argv[2]
	return file_name, server_ip


def main():
	file_name, server_ip = extract_arguments()
	client_socket = create_socket()
	meta_packet, chunks = file_to_chunks(file_name)

	send_all_chunks(client_socket, server_ip, meta_packet, chunks)

	client_socket.close()


main()
