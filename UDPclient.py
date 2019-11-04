#!/usr/bin/env python
# coding=utf-8

# A client that sends a file to a server using UDP-protocol #

# TODO:
# Compress file before sending


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
CHUNK_SIZE = 5000
WAIT_TIME_BETWEEN_CATCHES = 0.5
MAX_TIME_BETWEEN_PACKETS = 0.05
MAX_TRIES = 10
START_SEQUENCE_NUMBER = 100000
SERVER_PORT = 80
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


def create_file_meta_packet(file_name):
	size = os.stat(file_name).st_size # exists if not zero
	if (size == 0):
		print("invalid file size")
		sys.exit(0)

	sequence_nr = START_SEQUENCE_NUMBER
	size = int(size + (size / PACKET_SIZE) * 7)
	nr_of_data_packets = int(math.ceil(size / PACKET_SIZE))
	nr_of_chunks = int(math.ceil(nr_of_data_packets / CHUNK_SIZE))

	while True:
		if int(math.ceil((nr_of_data_packets + nr_of_chunks) / CHUNK_SIZE)) > nr_of_chunks:
			nr_of_chunks = int(math.ceil((nr_of_data_packets) + nr_of_chunks / CHUNK_SIZE))
		else:
			break

	meta = str(sequence_nr) + ";" + str(size) + ";" + file_name + ";" + str(nr_of_data_packets) + ";" + str(nr_of_chunks)
	return meta


def create_chunk_meta_packet(sequence_nr, remaining_packets):
	meta = str(sequence_nr) + ";"
	meta += (str(CHUNK_SIZE) if (int(remaining_packets // CHUNK_SIZE) > 0) else str(remaining_packets))

	return meta


def file_to_chunks(file_name):
	chunks = []
	packet_counter = 0
	chunk_nr = -1
	meta_packet = create_file_meta_packet(file_name)
	#nr_of_chunks = meta_packet.split(";")[-1]
	remaining_packets = int(meta_packet.split(";")[-2])

	sequence_nr = START_SEQUENCE_NUMBER

	with open(file_name, "r") as file:
		while True:
			sequence_nr += 1

			if packet_counter % CHUNK_SIZE == 0:
				chunks.append([])
				chunk_nr += 1
				chunks[chunk_nr].append(create_chunk_meta_packet(sequence_nr, remaining_packets))
				sequence_nr += 1
				packet_counter += 1

			data = file.read(PACKET_SIZE - len(str(sequence_nr)) - 1) # -1 to account for the delimeter
			if not data:
				break

			data = str(sequence_nr) + ";" + data
			chunks[chunk_nr].append(data)
			packet_counter += 1
			remaining_packets -= 1

	return meta_packet, chunks


def file_to_packets(file_name):
	packets = []
	sequence_nr = START_SEQUENCE_NUMBER

	with open(file_name, "r") as file: # create packets packets with PACKET_SIZE from file_name
		while True:
			sequence_nr += 1
			data = file.read(PACKET_SIZE - len(str(sequence_nr)) - 1) # -1 to account for the ";"
			if not data:
				break

			data = str(sequence_nr) + ";" + data
			packets.append(data)

	return packets


def extract_arguments():
	if len(sys.argv) != 3: # sys.argv=[file_name, server_ip]
		print("invalid arguments")
		sys.exit(0)

	file_name = sys.argv[1]
	server_ip = sys.argv[2]

	return file_name, server_ip


def send_all_chunks(client_socket, server_ip, meta_packet, chunks):
	print("send_all_chunks()")
	total_lost_packets = 0

	packets = []
	packets.append(meta_packet)
	for chunk in chunks: # get packets to 1d array
		for packet in chunk:
			packets.append(packet)

	while True:
		if send_meta_and_listen(client_socket, server_ip, meta_packet): # send file meta
			break
	print("meta success")

	for chunk in chunks: # send all chunks
		print("sending chunk")
		nr_of_lost_packets_in_chunk = 0
		nr_of_packets = len(chunk) - 1 # -1 to remove chunk meta

		while True: # send chunk meta
			if send_meta_and_listen(client_socket, server_ip, chunk[0]):
				break
		#print("chunk meta success, " + chunk[-1])

		for i in range(1, nr_of_packets): # send all packets
			client_socket.sendto(chunk[i].encode(), (server_ip, SERVER_PORT))
		print("dis how many: " + str(len(chunk)))
		print(str(chunk[1].split(";")[0]) + " first boi")
		print(str(chunk[-1].split(";")[0]) + " last boi")

		while True: # resend while there are any lost packets
			nr_of_lost_packets = listen_and_send_lost_packets(client_socket, server_ip, packets)
			if nr_of_lost_packets == 0:
				break

			nr_of_lost_packets_in_chunk += nr_of_lost_packets

		total_lost_packets += nr_of_lost_packets_in_chunk

	print("All chunks sent with a total of " + str(total_lost_packets) + " lost packets!")


def listen_and_send_lost_packets(client_socket, server_ip, packets):
	lost_packets = []
	lost_sequence_nrs = listen_for_lost_packets(client_socket)

	if len(lost_sequence_nrs) == 0:
		return 0

	for sequence_nr in lost_sequence_nrs:
		lost_packets.append(packets[int(sequence_nr)-START_SEQUENCE_NUMBER])

	#print(str(lost_sequence_nrs).strip('[]'))

	#print("-" + str(len(lost_sequence_nrs)) + " lost packets, resending")
	send_all(client_socket, server_ip, lost_packets)

	return len(lost_sequence_nrs)


def send_all(client_socket, server_ip, packets):
	for packet in packets:
		client_socket.sendto(packet.encode(),(server_ip, SERVER_PORT))



def send_all_packets(client_socket, server_ip, packets):
	nr_of_lost_packets = 0

	send_meta_and_listen(client_socket, server_ip, packets[0])

	for i in range(1, len(packets)): # Send all data packets, start at 1 because meta has already been sent
		client_socket.sendto(packets[i].encode(),(server_ip, SERVER_PORT))

	while True: # Listen for any packets lost
		lost_packets = []
		lost_sequence_nrs = []

		lost_sequence_nrs = listen_for_lost_packets(client_socket)

		nr_of_lost_packets += len(lost_sequence_nrs)
		if len(lost_sequence_nrs) == 0:
			print(str(len(packets)) + " " + str(nr_of_lost_packets))
			break

		for sequence_nr in lost_sequence_nrs:
			lost_packets.append(packets[int(sequence_nr)-START_SEQUENCE_NUMBER])

		for packet in lost_packets:
			client_socket.sendto(packet.encode(),(server_ip, SERVER_PORT)) # Send packet


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
			if incoming_packets and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # too long time between packets, calculate and send missing packets back
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


def main():
	file_name, server_ip = extract_arguments()
	client_socket = create_socket()
	#packets = file_to_packets(file_name)
	meta_packet, chunks = file_to_chunks(file_name)

	#send_all_packets(client_socket, server_ip, packets)
	send_all_chunks(client_socket, server_ip, meta_packet, chunks)

	client_socket.close()


main()
