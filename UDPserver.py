#!/usr/bin/env python
# coding=utf-8


import socket
import os
import sys
import time
import errno
import textwrap
import math

from file_manipulation import create_file_from_packets


PACKET_SIZE = 1024
SERVER_PORT = 80
CHUNK_SIZE = 2048
MAX_TIME_BETWEEN_PACKETS = 0.01
START_SEQUENCE_NUMBER = 100000
SERVER_DONE = "SERVER_DONE"
META = "META"
CHUNK = "CHUNK"


def reply_message(server_socket, client_address, message):
	server_socket.sendto(message.encode(), client_address)


def reply_lost_packets(server_socket, client_address, lost_packets):
	if len(lost_packets) == 0:
		reply_message(server_socket, client_address, SERVER_DONE)
		return True # return True because there are no lost packets to be received

	packets = []
	remaining_nrs = len(lost_packets)
	sequence_nrs_per_packet = PACKET_SIZE // 7 # 7 for len(seq_nr) + 1 for delimeter
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

	send_all(server_socket, client_address, packets)

	return False # return False because there are still lost packets to be received


def send_all(server_socket, client_address, packets):
	for packet in packets:
		server_socket.sendto(packet.encode(), client_address)


def extract_file_meta(file_meta):
	file_meta = file_meta.split(';')

	new_sequence_nr = int(file_meta[0])
	file_size = int(file_meta[1])
	file_name = file_meta[2]
	nr_of_packets = int(file_meta[3])
	nr_of_chunks = int(file_meta[4])

	return new_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks


def handle_socket_errors(error):
	if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
		return True
	else:
		print(error)
		sys.exit(1)


def get_remaining_chunk_sequence_nrs(start_sequence_nr, nr_of_packets):
	remaining_nrs = []
	for i in range(0, nr_of_packets):
		remaining_nrs.append(start_sequence_nr + i)

	return remaining_nrs


def receive_chunk(server_socket, chunk_sequence_nr, remaining_sequence_nrs):
	chunk = []
	new_packets = []
	remaining_nrs_in_chunk = []
	first_packet_received = False
	last_packet_time = 0

	while True:
		try:
			if first_packet_received and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # artificial timeout, reply lost packets
				chunk, remaining_nrs_in_chunk = artificial_timeout(chunk, chunk_sequence_nr, new_packets, remaining_nrs_in_chunk)
				new_packets = []
				first_packet_received = False
				if reply_lost_packets(server_socket, client_address, remaining_nrs_in_chunk):
					break

			packet, client_address = server_socket.recvfrom(PACKET_SIZE)

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()
			new_packets.append(packet)

			if not first_packet_received:
				first_packet_received = True

				incoming_sequence_nr = int(packet.split(";")[0])
				if incoming_sequence_nr == chunk_sequence_nr: # meta packet
					total_packets = int(packet.split(";")[1])
					remaining_nrs_in_chunk = get_remaining_chunk_sequence_nrs(chunk_sequence_nr, total_packets)
					reply_message(server_socket, client_address, CHUNK)

			last_packet_time = time.clock()

	return chunk


def receive_file_meta(server_socket):
	while True:
		try:
			packet, client_address = server_socket.recvfrom(PACKET_SIZE)

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()
			incoming_sequence_nr = int(packet.split(";")[0])
			if incoming_sequence_nr == START_SEQUENCE_NUMBER: # meta packet
				return packet, client_address


def receive_all_chunks(server_socket):
	print("\n--- READY TO RECEIVE FILE ---\n")
	chunks = []
	packets = []
	new_packets = []
	remaining_sequence_nrs = []
	first_sequence_nr = file_size = nr_of_packets = last_packet_time = nr_of_chunks = 0
	file_name = ""

	file_meta, client_address = receive_file_meta(server_socket)
	file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks = handle_meta_packet(file_meta)
	reply_message(server_socket, client_address, META) # send GO to client, making the client send all packets

	chunk_sequence_nrs = get_chunk_sequence_nrs(nr_of_chunks)

	for sequence_nr in chunk_sequence_nrs:
		chunks.append(receive_chunk(server_socket, sequence_nr, remaining_sequence_nrs))


	for chunk in chunks: # store all packets in a 1d lsit
		for packet in chunk[1:]: # remove chunk-meta packet from the data packets
			packets.append(packet[7:]) # remove sequence nr and delim from data packet

	print("--- ALL " + str(len(packets)) + " PACKETS RECEIVED! ---")
	return file_name, packets


def get_chunk_sequence_nrs(nr_of_chunks):
	sequence_nrs = []
	for i in range(0, nr_of_chunks):
		sequence_nrs.append((START_SEQUENCE_NUMBER + 1) + (i * CHUNK_SIZE)) # +1 to account for the file meta packet sequence nr (START_SEQUENCE_NUMBER)

	return sequence_nrs


def artificial_timeout(chunk, chunk_sequence_nr, new_packets, remaining_sequence_nrs):
	chunk, remaining_sequence_nrs = update_packets(chunk, new_packets, remaining_sequence_nrs)

	if len(remaining_sequence_nrs) != 0: # print information if there were lost packets
		padding = 7
		information = "-chunk: " + str(int((chunk_sequence_nr - START_SEQUENCE_NUMBER - 1) / CHUNK_SIZE)).ljust(padding)
		information += "new: " + str(len(new_packets)).ljust(padding)
		information += "remaining in chunk: " + str(len(remaining_sequence_nrs)).ljust(padding)
		information += "total: " + str(len(chunk)).ljust(padding)
		print(information)

	return chunk, remaining_sequence_nrs


def handle_meta_packet(packet):
	first_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks = extract_file_meta(packet)
	remaining_sequence_nrs = calculate_remaining_sequence_nrs(first_sequence_nr, nr_of_packets)

	return file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks


def update_packets(chunk, new_packets, remaining_sequence_nrs):
	for packet in new_packets:
		incoming_sequence_nr = int(packet.split(";")[0]) # extract sequence number
		if incoming_sequence_nr in remaining_sequence_nrs: # if incoming sequence number exists in remaining, remove it and add packet to 'packets'
			remaining_sequence_nrs.remove(incoming_sequence_nr)
			chunk.append(packet)

	return chunk, remaining_sequence_nrs


def calculate_remaining_sequence_nrs(first_sequence_nr, nr_of_packets):
	remaining_sequence_nrs = []

	for i in range(0, nr_of_packets): # append all sequence numbers
		remaining_sequence_nrs.append(first_sequence_nr + i)
	remaining_sequence_nrs.pop(0) # remove meta sequence_nr

	return remaining_sequence_nrs


def create_socket():
	server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)# create UDP socket
	server_socket.setblocking(False)
	server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server_socket.bind(('', SERVER_PORT)) # bind to specified port

	return server_socket


def main():
	server_socket = create_socket()
	file_name, packets = receive_all_chunks(server_socket)
	file_name = "copy_" + file_name
	path = "temp"
	file_name = os.path.join(path, file_name)

	if create_file_from_packets(file_name, packets):
		print("Successfully created " + file_name + " from " + str(len(packets)) + " packets!")

main()
