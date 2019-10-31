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
MAX_TIME_BETWEEN_PACKETS = 0.05
START_SEQUENCE_NUMBER = 100000
SERVER_DONE = "SERVER_DONE"
CLIENT_DONE = "CLIENT_DONE"
META = "META"


def reply_meta(server_socket, client_address):
	print("reply_meta()")
	server_socket.sendto("META".encode(), client_address)


def reply_server_done(server_socket, client_address):
	print("reply_server_done()")
	server_socket.sendto("SERVER_DONE".encode(), client_address)


def reply_lost_packets(server_socket, client_address, lost_packets):
	print("reply_lost_packets()")
	print("-" + str(len(lost_packets)) + " lost packets")
	if len(lost_packets) == 0:
		reply_server_done(server_socket, client_address)
		return True

	packets = []
	remaining_nrs = len(lost_packets)
	nrs_per_packet = PACKET_SIZE // 7 # 5 for seq nr + 1 for delimeter
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
		#print("-" + str(remaining_nrs) + " remaining")

	for packet in packets:
		#print("-sending lost packets")
		server_socket.sendto(packet.encode(), client_address)

	return False


def extract_meta(meta_packet):
	print("extract_meta()")
	meta_packet = meta_packet.split(';')

	new_sequence_nr = int(meta_packet[0])
	file_size = int(meta_packet[1])
	file_name = meta_packet[2]
	nr_of_packets = int(meta_packet[3])

	return new_sequence_nr, file_size, file_name, nr_of_packets


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
			error = e.args[0]
			if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
				continue
			else:
				print(error)
				sys.exit(1)

		else:
			packet = packet.decode()
			new_packets.append(packet)

			if not first_packet_received: # first packet handling
				first_packet_received = True
				if int(packet.split(";")[0]) == START_SEQUENCE_NUMBER: # meta packet
					file_size, file_name, nr_of_packets, remaining_sequence_nrs = handle_meta_packet(server_socket, client_address, packet)

			last_packet_time = time.clock()

	print("alles klar, " + str(len(packets)) + " packets received!")


def artificial_timeout(packets, new_packets, remaining_sequence_nrs):
	packets, remaining_sequence_nrs = update_packets(packets, new_packets, remaining_sequence_nrs)
	new_packets = []
	print("-" + str(len(new_packets)) + " new, " + str(len(remaining_sequence_nrs)) + " remaining" + ", " + str(len(packets)) + " total")

	return packets, remaining_sequence_nrs, new_packets


def handle_meta_packet(server_socket, client_address, packet):
	first_sequence_nr, file_size, file_name, nr_of_packets = extract_meta(packet) # extract meta packet
	remaining_sequence_nrs = get_remaining_sequence_nrs(first_sequence_nr, nr_of_packets) # calculate all remaining sequence numbers
	print("-" + str(len(remaining_sequence_nrs)) + " total packets")
	reply_meta(server_socket, client_address) # send GO to client

	return file_size, file_name, nr_of_packets, remaining_sequence_nrs


def update_packets(packets, new_packets, remaining_sequence_nrs):
	for packet in new_packets:
		inc_sequence_nr = int(packet.split(";")[0]) # extract sequence number
		if inc_sequence_nr in remaining_sequence_nrs: # if incoming sequence number exists in remaining, remove it and add packet to 'packets'
			remaining_sequence_nrs.remove(inc_sequence_nr)
			packets.append(packet)

	return packets, remaining_sequence_nrs


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
		receive_all(server_socket)


main()
