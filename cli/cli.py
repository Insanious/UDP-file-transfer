#!/usr/bin/env python


from commands import command_receive
from commands import command_send
from commands import command_exit


PROMPT = "<< "


def display_menu():
	padding = 20
	menu = " COMMANDS:\n"
	menu += " exit, quit, q".ljust(padding)
	menu += "-Exits the CLI\n"

	menu += " menu".ljust(padding)
	menu += "-Displays this menu\n"

	menu += " receive".ljust(padding)
	menu += "-Receive a file\n"

	menu += " send".ljust(padding)
	menu += "-Send a file\n"
	print(menu)


def command_action(command, arguments, options, flags):
	if command == "exit" or command == "quit" or command == "q":
		command_exit()
	elif command == "menu":
		display_menu()
	elif command == "receive":
		command_receive(arguments, options, flags)
	elif command == "send":
		command_send(arguments, options, flags)


def extract(parameters):
	parameters = parameters.split()
	command = ""
	arguments = []
	options = ""
	flags = ""

	if len(parameters) == 0:
		return command, arguments, options, flags

	command = parameters.pop(0)

	for parameter in parameters:
		arguments.append(parameter)

	return command, arguments, options, flags


def main():
	display_menu()

	while True:
		parameters = input(PROMPT)
		command, arguments, options, flags = extract(parameters)

		command_action(command, arguments, options, flags)


main()
