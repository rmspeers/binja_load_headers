"""
Copyright 2018 River Loop Security, LLC
rmspeers
"""

from binaryninja import *
from tempfile import mkdtemp
from shutil import copytree, rmtree
import fnmatch
import os
import pcpp
from copy import copy
import code


def make_working_dir(header_dir):
	temp_dir = mkdtemp()
	rmtree(temp_dir) # can't be there for copytree
	print("Copy to {}".format(temp_dir))
	copytree(header_dir, temp_dir, symlinks=False)
	return temp_dir


class OurPreprocessor(pcpp.Preprocessor):
	def __init__(self):
		super(OurPreprocessor, self).__init__()
		self.line_directive = '//line'
		self.__tok_buffer = []
		self.__tok_buffer_flushing = False
		self._template_token = None

	def on_include_not_found(self,is_system_include,curdir,includepath):
		#return None
		raise pcpp.OutputDirective()

	def __mint_token(self, type, value):
		"""
		Create a LexToken of the given type and value.
		:param type:
		:param value:
		:return:
		"""
		tok = copy(self._template_token)
		tok.lineno = 0
		tok.lexpos = 0
		tok.value = value
		tok.type = type
		return tok

	def __update_list_and_return(self, last_tok, return_first_element=False, finalize=False):
		self.__tok_buffer.append(last_tok)
		#print("added {} to buffer: {}".format(last_tok, self.__tok_buffer))
		if finalize:
			#print("marking to flush")
			self.__tok_buffer_flushing = True
		else:
			pass #print("flushing status marked as : {}".format(self.__tok_buffer_flushing))
		if return_first_element:
			#print("Returning real token: {}".format(self.__tok_buffer[0]))
			return self.__tok_buffer.pop(0)
		else:
			return self.__mint_token('CPP_WS', ' ')

	@staticmethod
	def __scan_to_item(tok_list, match_func, adjust_i=0, backwards=False):
		"""
		Utility function to find an item
		:param tok_list: list of LexToken's to search over
		:param match_func: lambda function that returns true when it's the element you want
		:param adjust_i: offset to adjust result by, e.g. if you what the index of the element before the match, provide -1
		:param backwards: search from end of list if True
		:return:
		"""
		cur_tok_i = -1 if backwards else 0
		while not match_func(tok_list[cur_tok_i]):
			print("Didn't match: {}".format(tok_list[cur_tok_i]))
			cur_tok_i += -1 if backwards else 1
		cur_tok_i += adjust_i
		return cur_tok_i

	def _update_enum_buf(self, tok_list):
		#print("Original Enum Buf: {}".format(tok_list))
		typedef_token = tok_list.pop(0)  # get rid of typedef
		# handles cases where there may be whitespace around the name at the end of the enum:
		name_token_i = self.__scan_to_item(tok_list, lambda t: t.type == 'CPP_ID', backwards=True)
		name_token = tok_list[name_token_i]
		print("Got name at {}: {}".format(name_token_i, name_token))
		# setup the start like: enum ..._e
		tmp = tok_list[0]
		tok_list[0] = tok_list[1]
		tok_list[1] = tmp
		tok_list.insert(2, self.__mint_token(name_token.type, name_token.value + '_e'))
		# remove any trailing comma in the enum block:
		cur_tok_i = self.__scan_to_item(tok_list, lambda t: t.type == '}', adjust_i=-1, backwards=True)
		print("Starting comma search at: {}\n{}".format(tok_list[cur_tok_i], tok_list))
		while tok_list[cur_tok_i].type == 'CPP_WS':
			cur_tok_i -= 1
			if tok_list[cur_tok_i].type == ',':
				print("deleting comma at {}: {}".format(cur_tok_i, tok_list[cur_tok_i]))
				del tok_list[cur_tok_i]
				break
		# close out the enum with ;\n
		tok_list.insert(name_token_i, self.__mint_token(';', ';'))
		tok_list.insert(name_token_i, self.__mint_token('CPP_WS', '\n'))
		# add a typedef line like: typedef ..._e ...;
		tok_list.insert(name_token_i, typedef_token)
		tok_list.insert(name_token_i, self.__mint_token('CPP_WS', ' '))
		tok_list.insert(name_token_i, self.__mint_token(name_token.type, name_token.value + '_e'))
		tok_list.insert(name_token_i, self.__mint_token('CPP_WS', ' '))
		print("New Enum Buf: {}".format(tok_list))
		return tok_list

	def token(self):
		"""Method to return individual tokens"""
		#print("Entered token() ---")
		# Else collect:
		try:
			while True:
				# If we have stuff to spit out, do it:
				#print("Entered loop true ---")
				if self.__tok_buffer_flushing and len(self.__tok_buffer) > 0:
					#print("popping from buffer: {}".format(self.__tok_buffer))
					return self.__tok_buffer.pop(0)
				elif self.__tok_buffer_flushing:
					#print("-- done flushing")
					self.__tok_buffer_flushing = False
					self.__tok_buffer = []
				# Get and process the next token
				tok = next(self.parser)
				if tok.type not in self.ignore:
					if self._template_token is None:
						self._template_token = tok
					#print("tokenized: {}".format(tok))
					if tok.value == 'typedef':
						if len(self.__tok_buffer) != 0:  # TODO sanity check here that it's empty
							print("Buffer contains something when SHOULD NOT: {}".format(self.__tok_buffer))
						return self.__update_list_and_return(tok, finalize=False)
					elif len(self.__tok_buffer) == 2:
						if tok.value != 'enum': # we didn't get typedef, ,enum -- so stop collecting
							self.__update_list_and_return(tok, return_first_element=False, finalize=True)
						else: # if we now have typedef, , enum
							self.__tok_buffer.append(tok)
							#print("should be a whitespace token available: {} or {}".format(self.__tok_buffer[1], self.__mint_token('CPP_WS', ' ')))
							return self.__tok_buffer[1]
							#self.__update_list_and_return
					elif len(self.__tok_buffer) > 0 and tok.value == ';':
						self.__tok_buffer.append(tok)
						self.__tok_buffer_flushing = True
						print("Completed gathering info ====")
						self.__tok_buffer = self._update_enum_buf(self.__tok_buffer)
						return self.__tok_buffer.pop(0)  # should return enum
					elif len(self.__tok_buffer) > 0:
						return self.__update_list_and_return(tok, finalize=False)
						#self.__tok_buffer.append(tok)
						#return self.__mint_token('CPP_WS', ' ')
					else:
						return tok
		except StopIteration:
			self.parser = None
			return None


def get_all_header_files(path):
	for root, dirnames, filenames in os.walk(path):
		for filename in fnmatch.filter(filenames, '*.h'):
			yield os.path.join(root, filename)
	raise StopIteration


def sanitize_files(header_dir, header_file_path):
	for f in [header_file_path]: #get_all_header_files(header_dir):
		print(f)
		pp = OurPreprocessor()
		pp.add_path(header_dir)
		with open(f, 'r') as fh:
			fc = fh.read()
			pp.parse(fc)
		with open(f, 'w') as fho:
			pp.write(fho)


def process(bv, dir_name, header_file):
	temp_dir = make_working_dir(dir_name)
	header_file_path = os.path.join(dir_name, './'+header_file)
	assert os.path.isfile(header_file_path)
	sanitize_files(temp_dir, header_file_path)

	parsed_data = None
	try:
		parsed_data = bv.platform.parse_types_from_source_file(header_file_path) #, include_dirs=[temp_dir])
	except NameError as e:
		print("Unable to set parse types from the source, likely as not running in BinjaScript with bv defined: {}".format(e))
	except Exception as e:
		print("Unable to set parse types from the source, likely as something was unable to be fixed in the input files to BinaryNinja's satisfaction: {}".format(e))

	if parsed_data is not None:
		parsed_types = parsed_data.types
		for type_name, type_obj in parsed_types.items():
			#print("Parsed from headers: {}\t{}".format(type_name, type_obj))
			bv.define_user_type(type_name, type_obj)
		for func in bv.functions:
			if func.name in parsed_data.functions:
				func_type = parsed_data.functions[func.name]
				print("Setting data for function {} to type {}".format(func.name, func_type))
				func.function_type = func_type
			else:
				print("Didn't find data for function: {}".format(func.name))
				#code.interact(local=locals())
				#break
	else:
		print("Parsed data is none.")


def get_input(bv,function):
	dir_name = get_directory_name_input("Select folder containing headers.")
	if dir_name is None:
		show_message_box("Error", "Must specify a folder")
	header_file = get_open_filename_input("Select main header file.")
	if header_file is None:
		show_message_box("Error", "Must specify the primary header file to load")
	# convert header_file to be relative to dir_name:
	prefix = os.path.commonprefix([dir_name, header_file])
	if len(prefix) > 0:
		header_file = header_file[len(prefix):]
		test_header_path = os.path.join(dir_name, './'+header_file)
		if not os.path.isfile(test_header_path):
			show_message_box("Error", "Header path after manipulation is invalid: {}".format(test_header_path))
	process(bv, dir_name, header_file)


if __name__=='__main__':
	lib_file = get_open_filename_input("Select binary file to analyze.")
	bv = binaryninja.BinaryViewType["ELF"].open(lib_file)
	dir_name = get_directory_name_input("Select folder containing headers.")
	header_file = get_open_filename_input("Select file within that folder to use.")
	process(bv, dir_name, header_file)
else:
	PluginCommand.register_for_address("Load Header Files", "Parses header files to assist with analysis.", get_input)
