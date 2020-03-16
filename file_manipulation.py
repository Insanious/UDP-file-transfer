#!/usr/bin/env python


import shutil
import os


def create_file_from_packets(file_name, packets):
	print("Creating file...")
	with open(file_name, "w+") as file:
		for packet in packets:
			file.write(packet)

	return True

def create_file_from_binary_packets(file_name, packets):
	print("Creating file...")
	with open(file_name + ".zip", "wb+") as file:
		for packet in packets:
			file.write(packet)

	shutil.unpack_archive(file_name + ".zip", "./temp", "zip")
	os.remove(file_name + ".zip")

	return True
