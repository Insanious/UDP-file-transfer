#!/usr/bin/env python
# coding=utf-8

# TODO:
# Decompress file after receiving

import socket
import os
import sys
import time
import errno
import textwrap
import math

PACKET_SIZE = 1024
SERVER_PORT = 80
CHUNK_SIZE = 5000
MAX_TIME_BETWEEN_PACKETS = 0.05
START_SEQUENCE_NUMBER = 100000
SERVER_DONE = "SERVER_DONE"
META = "META"
CHUNK = "CHUNK"


def reply_message(server_socket, client_address, message):
	server_socket.sendto(message.encode(), client_address)


def reply_lost_packets(server_socket, client_address, lost_packets):
	print("reply_lost_packets()")
	print("-" + str(len(lost_packets)) + " lost packets")
	if len(lost_packets) == 0:
		reply_message(server_socket, client_address, SERVER_DONE)
		return True
	#print(str(lost_packets).strip('[]'))

	packets = []
	remaining_nrs = len(lost_packets)
	nrs_per_packet = PACKET_SIZE // 7 # 7 for seq nr + 1 for delimeter
	nr_of = nrs_per_packet
	counter = 0

	while remaining_nrs > 0:
		packet = ""

		if remaining_nrs < nrs_per_packet:
			nr_of = remaining_nrs
		remaining_nrs -= nr_of

		for i in range(0, nr_of):
			packet += str(lost_packets[counter]) + ";"
			counter += 1

		packets.append(packet)

	for packet in packets:
		server_socket.sendto(packet.encode(), client_address)

	return False


def extract_meta(meta_packet):
	print("extract_meta()")
	meta_packet = meta_packet.split(';')

	new_sequence_nr = int(meta_packet[0])
	file_size = int(meta_packet[1])
	file_name = meta_packet[2]
	nr_of_packets = int(meta_packet[3])
	nr_of_chunks = int(meta_packet[4])

	return new_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks


def handle_socket_errors(error):
	if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
		return True
	else:
		print(error)
		sys.exit(1)


def get_remaining_chunk_nrs(start_sequence_nr, nr_of_packets):
	remaining_nrs = []
	for i in range(0, nr_of_packets):
		remaining_nrs.append(start_sequence_nr + i)

	return remaining_nrs


def receive_chunk(server_socket, chunk_sequence_nr, remaining_sequence_nrs):
	print("Receieving chunk " + str(chunk_sequence_nr))
	chunk = []
	new_packets = []
	remaining_nrs_in_chunk = []
	first_packet_received = False
	last_packet_time = 0

	while True:
		try:
			if first_packet_received and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # artificial timeout, reply lost packets
				print(str(new_packets[0].split(";")[0]) + " is dis first")
				print(str(new_packets[-1].split(";")[0]) + " is dis last")
				chunk, remaining_nrs_in_chunk, new_packets = artificial_timeout(chunk, new_packets, remaining_nrs_in_chunk)
				first_packet_received = False
				if reply_lost_packets(server_socket, client_address, remaining_nrs_in_chunk):
					break
				print("-lost packets sent")

			packet, client_address = server_socket.recvfrom(PACKET_SIZE)

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()
			new_packets.append(packet)

			if not first_packet_received:
				first_packet_received = True
				if int(packet.split(";")[0]) == chunk_sequence_nr: # meta packet
					remaining_nrs_in_chunk = get_remaining_chunk_nrs(chunk_sequence_nr, int(packet.split(";")[1]))
					reply_message(server_socket, client_address, CHUNK)

			last_packet_time = time.clock()

	return chunk


def receive_all_chunks(server_socket):
	print("\n---READY TO RECEIVE NEW CHUNKS---\n")
	chunks = []
	packets = []
	new_packets = []
	remaining_sequence_nrs = []
	first_sequence_nr = file_size = nr_of_packets = last_packet_time = nr_of_chunks = 0
	file_name = ""

	while True: # get meta packet
		try:
			packet, client_address = server_socket.recvfrom(PACKET_SIZE)

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()

			if int(packet.split(";")[0]) == START_SEQUENCE_NUMBER: # meta packet
				file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks = handle_meta_packet(server_socket, client_address, packet)
				print("nr of cunks:" + str(nr_of_chunks))
				packets.append(packet)
				break

	chunk_sequence_nrs = get_chunk_sequence_nrs(nr_of_chunks)

	for i in range(0, nr_of_chunks):
		chunks.append(receive_chunk(server_socket, chunk_sequence_nrs[i], remaining_sequence_nrs))


def get_chunk_sequence_nrs(nr_of_chunks):
	sequence_nrs = []

	for i in range(0, nr_of_chunks):
		sequence_nrs.append((START_SEQUENCE_NUMBER + 1) + (i * CHUNK_SIZE)) # +1 to account for the file meta packet at 0

	return sequence_nrs


def receive_all(server_socket):
	print("\n---READY TO RECEIVE NEW FILE---\n")
	packets = []
	new_packets = []
	remaining_sequence_nrs = []
	first_sequence_nr = file_size = nr_of_packets = last_packet_time = 0
	first_packet_received = False
	file_name = ""

	while True:
		try:
			if first_packet_received and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # artificial timeout, reply lost packets
				packets, remaining_sequence_nrs, new_packets = artificial_timeout(packets, new_packets, remaining_sequence_nrs)
				first_packet_received = False
				if reply_lost_packets(server_socket, client_address, remaining_sequence_nrs):
					break
				print("-lost packets sent")

			packet, client_address = server_socket.recvfrom(PACKET_SIZE) # recieve next packet

		except socket.error as e:
			if handle_socket_errors(e.args[0]):
				continue

		else:
			packet = packet.decode()
			new_packets.append(packet)

			if not first_packet_received: # first packet handling
				first_packet_received = True
				if int(packet.split(";")[0]) == START_SEQUENCE_NUMBER: # meta packet
					file_size, file_name, nr_of_packets, remaining_sequence_nrs = handle_meta_packet(server_socket, client_address, packet)

			last_packet_time = time.clock()

	print("alles klar, " + str(len(packets)) + " packets received!")


def artificial_timeout(chunk, new_packets, remaining_sequence_nrs):
	chunk, remaining_sequence_nrs = update_packets(chunk, new_packets, remaining_sequence_nrs)
	print("-" + str(len(new_packets)) + " new, " + str(len(remaining_sequence_nrs)) + " remaining" + ", " + str(len(chunk)) + " total")
	new_packets = []

	return chunk, remaining_sequence_nrs, new_packets


def handle_meta_packet(server_socket, client_address, packet):
	first_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks = extract_meta(packet) # extract meta packet
	remaining_sequence_nrs = get_remaining_sequence_nrs(first_sequence_nr, nr_of_packets) # calculate all remaining sequence numbers
	print("-meta received, " + str(len(remaining_sequence_nrs)) + " total packets")
	reply_message(server_socket, client_address, META) # send GO to client

	return file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks


def update_packets(chunk, new_packets, remaining_sequence_nrs):
	for packet in new_packets:
		inc_sequence_nr = int(packet.split(";")[0]) # extract sequence number
		if inc_sequence_nr in remaining_sequence_nrs: # if incoming sequence number exists in remaining, remove it and add packet to 'packets'
			remaining_sequence_nrs.remove(inc_sequence_nr)
			chunk.append(packet)

	return chunk, remaining_sequence_nrs


def get_remaining_sequence_nrs(first_sequence_nr, nr_of_packets):
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
	while True:
		receive_all_chunks(server_socket)


main()
