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
WAIT_TIME_BETWEEN_CATCHES = 0.5
MAX_TIME_BETWEEN_PACKETS = 0.05
MAX_TRIES = 10
START_SEQUENCE_NUMBER = 100000
SERVER_PORT = 80
SERVER_DONE = "SERVER_DONE"
META = "META"


def format_lost_packets(lost_packets):
	sequence_nrs = []
	# check if empty???

	for packet in lost_packets:
		splitted = packet.split(";")
		splitted = splitted[:-1]
		#print(str(len(sequence_nrs)) + " splitnr")
		# print(', '.join(splitted))

		for sequence_nr in splitted:
			sequence_nrs.append(int(sequence_nr))

	return sequence_nrs


def send_meta_and_listen(client_socket, server_ip, meta_packet):
	#print("send_meta_and_listen()")

	while True:
		#print("-sending meta")
		client_socket.sendto(meta_packet.encode(),(server_ip, SERVER_PORT)) # Send meta-packet
		meta_sent_time = time.clock()

		while True:
			if time.clock() - meta_sent_time > META_RESEND_TIME: # resend meta
				break
			try:
				response, server_address = client_socket.recvfrom(PACKET_SIZE)
			except socket.error as e:
				error = e.args[0]
				if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
					continue
				else:
					print(e)
					sys.exit(1)
			else:
				if (response.decode() == META):
					#print("-meta handshake received")
					return



def file_to_packets(file_name):
	packets = [];
	size = os.stat(file_name).st_size # exists if not zero
	if (size == 0):
		print("invalid file size")
		sys.exit(0)

	sequence_nr = START_SEQUENCE_NUMBER
	size = int(size + (size / PACKET_SIZE) * 7)
	nr_of_packets = int(math.ceil(size / PACKET_SIZE))

	meta_packet = str(sequence_nr) + ";" + str(size) + ";" + file_name + ";" + str(nr_of_packets)
	packets.append(meta_packet)

	#print(packets[0])

	with open(file_name, "r") as file: # create packets packets with PACKET_SIZE from file_name
		while True:
			sequence_nr += 1
			data = file.read(PACKET_SIZE - len(str(sequence_nr)) - 1) # -1 to account for the ";"
			if not data:
				break

			data = str(sequence_nr) + ";" + data
			packets.append(data)

	#print("nr_of: " + str(len(packets)))
	return packets


def extract_arguments():
	if len(sys.argv) != 3: # sys.argv=[file_name, server_ip]
		print("invalid arguments")
		sys.exit(0)

	file_name = sys.argv[1]
	server_ip = sys.argv[2]

	return file_name, server_ip


def send_all_packets(client_socket, server_ip, packets):
	#print("send_all_packets()")
	nr_of_lost_packets = 0
	send_meta_and_listen(client_socket, server_ip, packets[0])

	for i in range(1, len(packets)): # Send all data packets, start at 1 because meta has already been sent
		client_socket.sendto(packets[i].encode(),(server_ip, SERVER_PORT))
	#print("-sent packets for the first time")

	while True: # Listen for any packets lost
		lost_packets = []
		lost_sequence_nrs = []

		lost_sequence_nrs = listen_for_lost_packets(client_socket)

		#print(str(len(lost_sequence_nrs)) + " nrs remaining")
		nr_of_lost_packets += len(lost_sequence_nrs)
		if len(lost_sequence_nrs) == 0:
			print(str(len(packets)) + " " + str(nr_of_lost_packets))
			break

		for sequence_nr in lost_sequence_nrs:
			lost_packets.append(packets[int(sequence_nr)-START_SEQUENCE_NUMBER])

		#print("-sending " + str(len(lost_packets)) + " lost packets")
		for packet in lost_packets:
			client_socket.sendto(packet.encode(),(server_ip, SERVER_PORT)) # Send packet


def listen_for_lost_packets(client_socket):
	#print("listen_for_lost_packets()")
	lost_sequence_nrs = []
	incoming_packets = False;
	last_packet_time = time.clock()

	while True:
		try:
			if incoming_packets and time.clock() - last_packet_time > MAX_TIME_BETWEEN_PACKETS: # too long time between packets, calculate and send missing packets back
				#print("-artificial timeout")
				return format_lost_packets(lost_sequence_nrs)

			packet, server_address = client_socket.recvfrom(PACKET_SIZE)
		except socket.error as e:
			error = e.args[0]
			if error == errno.EAGAIN or error == errno.EWOULDBLOCK:
				continue
			else:
				print(error)
				sys.exit(1)

		else:
			packet = packet.decode()
			# first packet
			if not incoming_packets:
				#print("-first packet arrived")
				incoming_packets = True

			if packet == SERVER_DONE:
				#print(packet)
				return []
			#print("-lost nrs received")
			lost_sequence_nrs.append(packet)
			last_packet_time = time.clock()


def main():
	file_name, server_ip = extract_arguments()

	client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	client_socket.setblocking(False)

	send_all_packets(client_socket, server_ip, file_to_packets(file_name))

	#print("closing socket")
	client_socket.close()


main()
