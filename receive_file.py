#!/usr/bin/env python
# coding=utf-8


import logging
import argparse
import os

from server.Server import Server
from utilities.file_manipulation import *


logger = logging.getLogger(__name__)


def receive_file():
	server = Server()
	file_name, packets = server.receive_all_chunks()

	file_name = "copy_" + file_name
	path = "temp"
	file_name = os.path.join(path, file_name)

	if create_file_from_packets(file_name, packets):
		logger.info(f"Successfully created {file_name} from {len(packets)} packets")
	else:
		logger.error(f"error creating file {file_name}")


def main():
	parser = argparse.ArgumentParser(description="Receive a file from a client")
	parser.add_argument("-log", metavar="--log_level", type=str, help="the log level")

	log_level = vars(parser.parse_args())["log"]
	log_level = log_level.upper() if log_level != None else "WARNING"

	logging.basicConfig(level=log_level)

	logger.setLevel(log_level)

	receive_file();


if __name__ == "__main__":
	main()
