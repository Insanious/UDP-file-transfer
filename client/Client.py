#!/usr/bin/env python


import socket
import time
import errno

from utilities.utilities import *


class Client:
	META_RESEND_TIME = 0.5
	PACKET_SIZE = 1024
	SERVER_PORT = 80
	CHUNK_SIZE = 2048
	MAX_TIME_BETWEEN_PACKETS = 0.01
	START_SEQUENCE_NUMBER = 100000
	SERVER_DONE = "SERVER_DONE"
	META = "META"
	CHUNK = "CHUNK"


	def __init__(self, server_ip):
		self.logger = logging.getLogger(__name__)

		self.server_ip = server_ip
		self.socket = create_client_socket()


	def close_socket(self):
		self.socket.close()


	def send_meta_and_listen(self, meta_packet):
		'''
		Send a single meta-packet and try to get a self.META or self.CHUNK response under self.META_RESEND_TIME seconds.
		'''
		while True:
			self.socket.sendto(meta_packet.encode(),(self.server_ip, self.SERVER_PORT)) # Send meta-packet
			meta_sent_time = time.clock()

			while True:
				if time.clock() - meta_sent_time > self.META_RESEND_TIME: # resend meta
					return False
				try:
					response, server_address = self.socket.recvfrom(self.PACKET_SIZE)
				except socket.error as e:
					if handle_socket_errors(e.args[0]):
						continue
				else:
					response = response.decode()
					if response == self.META or response == self.CHUNK:
						self.logger.info("got response")
						return True


	def send_all_archive_chunks(self, meta_packet, chunks):
		total_lost_packets = 0

		packets = []
		packets.append(meta_packet)
		for chunk in chunks: # get packets to 1d array
			for packet in chunk:
				packets.append(packet)

		while True:
			self.logger.info("sending file meta packet")
			if self.send_meta_and_listen(meta_packet): # send file meta
				break

		for chunk in chunks: # send all chunks
			nr_of_lost_packets_in_chunk = 0

			while True: # send chunk meta
				self.logger.info("sending chunk meta packet")
				if self.send_meta_and_listen(chunk[0].decode()):
					_chunk = chunk[0].decode()
					chunk_nr = (get_sequence_nr(_chunk) - self.START_SEQUENCE_NUMBER + 1) / self.CHUNK_SIZE
					break

			self.logger.info(f"sending chunk {chunk_nr}")
			#print("-SENDING CHUNK " + str(int(chunk_nr)))

			self.send_all(chunk[1:]) # send all packets except the first, which has already been sent (meta-chunk)

			nr_of_lost_packets = self.listen_and_send_lost_packets(packets)
			while nr_of_lost_packets != 0: # resend packets while there are any lost packets
				nr_of_lost_packets_in_chunk += nr_of_lost_packets
				nr_of_lost_packets = self.listen_and_send_lost_packets(packets)

			total_lost_packets += nr_of_lost_packets_in_chunk

		count = 0
		for chunk in chunks:
			count += len(chunk) - 1

		print("All chunks sent with a total of " + str(total_lost_packets) + " lost packets out of " + str(count) + "!")


	def send_all_file_chunks(self, meta_packet, chunks):
		total_lost_packets = 0

		packets = []
		packets.append(meta_packet)
		for chunk in chunks: # get packets to 1d array
			for packet in chunk:
				packets.append(packet)

		while True:
			self.logger.info("sending file meta packet")
			if self.send_meta_and_listen(meta_packet): # send file meta
				break

		for chunk in chunks: # send all chunks
			nr_of_lost_packets_in_chunk = 0

			while True: # send chunk meta
				self.logger.info("sending chunk meta packet")
				if self.send_meta_and_listen(chunk[0]):
					chunk_nr = (get_sequence_nr(chunk[0]) - self.START_SEQUENCE_NUMBER + 1) // self.CHUNK_SIZE
					break

			self.logger.info(f"sending chunk {chunk_nr}")

			self.send_all(chunk[1:]) # send all packets except the first, which has already been sent (meta-chunk)

			nr_of_lost_packets = self.listen_and_send_lost_packets(packets)

			while nr_of_lost_packets != 0: # resend packets while there are any lost packets
				nr_of_lost_packets_in_chunk += nr_of_lost_packets
				nr_of_lost_packets = self.listen_and_send_lost_packets(packets)

			total_lost_packets += nr_of_lost_packets_in_chunk

		count = 0
		for chunk in chunks:
			count += len(chunk) - 1

		self.logger.info(f"All chunks sent with a total of {total_lost_packets} lost packets out of {count}")


	def listen_and_send_lost_packets(self, packets):
		lost_packets = []
		lost_sequence_nrs = self.listen_for_lost_packets()
		nr_of_lost_packets = len(lost_sequence_nrs)

		if nr_of_lost_packets == 0: # happens when server sends SERVER_DONE
			self.logger.info("no more packets to send in chunk")
			return 0

		for sequence_nr in lost_sequence_nrs:
			lost_packets.append(packets[int(sequence_nr)-self.START_SEQUENCE_NUMBER]) # packet_index = seq - start_seq

		self.logger.info(f"sending {nr_of_lost_packets} lost packets to server")
		self.send_all(lost_packets)

		return nr_of_lost_packets


	def send_all(self, packets):
		for packet in packets:
			self.socket.sendto(packet.encode(), (self.server_ip, self.SERVER_PORT))


	def listen_for_lost_packets(self):
		lost_sequence_nrs = []
		incoming_packets = False
		last_packet_time = 0

		while True:
			try:
				if incoming_packets and time.clock() - last_packet_time > self.MAX_TIME_BETWEEN_PACKETS: # too long time between packets
					return format_lost_packets(lost_sequence_nrs)

				packet, server_address = self.socket.recvfrom(self.PACKET_SIZE)

			except socket.error as e:
				if handle_socket_errors(e.args[0]):
					continue

			else:
				packet = packet.decode()

				if not incoming_packets: # first packet
					incoming_packets = True

				if packet == self.SERVER_DONE:
					return []

				lost_sequence_nrs.append(packet)
				last_packet_time = time.clock()
