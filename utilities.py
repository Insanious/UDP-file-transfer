#!/usr/bin/env python


import errno
import socket


def handle_socket_errors(error):
	if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
		return True
	else:
		print(error)
		sys.exit(1)

def format_lost_packets(lost_packets):
	sequence_nrs = []

	for packet in lost_packets:
		splitted = packet.split(";")
		splitted = splitted[:-1]
		for sequence_nr in splitted:
			sequence_nrs.append(int(sequence_nr))

	return sequence_nrs

def create_client_socket():
	client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	client_socket.setblocking(False)

	return client_socket

def create_server_socket(server_port):
	server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)# create UDP socket
	server_socket.setblocking(False)
	server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server_socket.bind(('', server_port)) # bind to specified port

	return server_socket

def get_remaining_chunk_sequence_nrs(start_sequence_nr, nr_of_packets):
	remaining_nrs = []
	for i in range(0, nr_of_packets):
		remaining_nrs.append(start_sequence_nr + i)

	return remaining_nrs

def get_chunk_sequence_nrs(start_sequence_nr, chunk_size, nr_of_chunks):
	sequence_nrs = []
	for i in range(0, nr_of_chunks):
		sequence_nrs.append((start_sequence_nr + 1) + (i * chunk_size)) # +1 to account for the file meta packet seq nr (start_sequence_nr)

	return sequence_nrs

def update_packets(chunk, new_packets, remaining_sequence_nrs):
	for packet in new_packets:
		incoming_sequence_nr = ""
		for i in range(0, 6):
			incoming_sequence_nr += str(chr(packet[i]))
		incoming_sequence_nr = int(incoming_sequence_nr) # extract sequence number
		if incoming_sequence_nr in remaining_sequence_nrs: # if incoming sequence number exists in remaining, remove it and add packet to 'packets'
			remaining_sequence_nrs.remove(incoming_sequence_nr)
			chunk.append(packet)

	return chunk, remaining_sequence_nrs

def extract_file_meta(file_meta):
	file_meta = file_meta.split(';')

	new_sequence_nr = int(file_meta[0])
	file_size = int(file_meta[1])
	file_name = file_meta[2]
	nr_of_packets = int(file_meta[3])
	nr_of_chunks = int(file_meta[4])

	return new_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks

def calculate_remaining_sequence_nrs(first_sequence_nr, nr_of_packets):
	remaining_sequence_nrs = []

	for i in range(0, nr_of_packets): # append all sequence numbers
		remaining_sequence_nrs.append(first_sequence_nr + i)
	remaining_sequence_nrs.pop(0) # remove meta sequence_nr

	return remaining_sequence_nrs

def handle_meta_packet(packet):
	first_sequence_nr, file_size, file_name, nr_of_packets, nr_of_chunks = extract_file_meta(packet)
	remaining_sequence_nrs = calculate_remaining_sequence_nrs(first_sequence_nr, nr_of_packets)

	return file_size, file_name, nr_of_packets, remaining_sequence_nrs, nr_of_chunks

def extract_chunk_meta(packet, chunk_sequence_nr):
	incoming_sequence_nr = ""
	for i in range(0, 6):
		incoming_sequence_nr += str(chr(packet[i]))

	if int(incoming_sequence_nr) != chunk_sequence_nr:
		return -1

	total_packets = ""
	i = len(incoming_sequence_nr)
	while True:
		try:
			i += 1
			val = str(chr(packet[i]))
		except:
			break
		else:
			total_packets += val

	return int(total_packets)
