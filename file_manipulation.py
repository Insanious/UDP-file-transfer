#!/usr/bin/env python
# coding=utf-8

def create_file_from_packets(file_name, packets):
	print("Creating file...")
	with open(file_name, "w+") as file:
		for packet in packets:
			file.write(packet)

	return True
