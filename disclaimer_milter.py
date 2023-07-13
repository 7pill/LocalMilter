#!/usr/bin/python3
## To roll your own milter, create a class that extends Milter.
#  See the pymilter project at https://pymilter.org based
#  on Sendmail's milter API
#  More information about Milter module can be found at https://pythonhosted.org/pymilter/


import Milter
from Milter.utils import parse_addr
from io import BytesIO
import time
import base64
import email
import re
import os
import sys
from multiprocessing import Process as Thread, Queue


port_listen = 9999


logq = None


# Load data from file
file_path = os.path.abspath(__file__)
base_dir = os.path.dirname(file_path)
with open(base_dir + '/exception_domains.txt', 'r') as f:
	disclaimer_exception = f.read().split()
with open(base_dir + '/data/disclaimer_message.txt', 'r') as f:
	disclaimer_msg_txt = f.read() + '\n\n'
with open(base_dir + '/data/disclaimer_message.html', 'r') as f:
	disclaimer_msg_html = f.read() + '\n\n'




class myMilter(Milter.Base):
	def __init__(self):
		self.id = Milter.uniqueID()	# Integer incremented with each call.
		self.fromExternal = True

		self.fromHeader = ''


	# each connection runs in its own thread and has its own myMilter
	# instance. Python code must be thread safe. This is trivial if only stuff
	# in myMilter instances is referenced.

	
	def envfrom(self, mailfrom, *str):
		self.log("mail from:", mailfrom, *str)
		# NOTE: self.fp is only en *internal* copy of message data. You
		# must use addheader, chgheader, replacebody to change the message
		# on the MTA

		# Verify if email send from External
		sender_address = mailfrom[1:-1]
		self.fromExternal = not any([re.fullmatch(pattern, sender_address) for pattern in disclaimer_exception])
		# self.log("sender domain: ", sender_domain)
		if self.fromExternal:
			self.fp = BytesIO()
			return Milter.CONTINUE
		else:
			return Milter.ACCEPT		

	
	@Milter.noreply
	def header(self, name, hval):
		if name == 'From':
			self.fromHeader = hval
		elif name == "Content-Type" or name == "Content-Transfer-Encoding":
			self.fp.write(b'%s: %s\n' % (name.encode(),hval.encode()))	# add header to buffer
		return Milter.CONTINUE

	
	@Milter.noreply
	def eoh(self):
		self.fp.write(b'\n')				# terminate headers
		return Milter.CONTINUE

	
	def body(self, chunk):					# Get copy of body message data on buffer
		self.fp.write(chunk)
		return Milter.CONTINUE


	def eom(self):
		# many milter functions can only be called from eom()	
		if self.fromExternal:
			# Add Disclaimer header.
			self.addheader('X-Disclaimer-Present', 'Yes')

			# Add Disclaimer message
			self.fp.seek(0)
			msg = email.message_from_binary_file(self.fp) 		# msg holds the entire message body
			msg = embed_disclaimer(msg, disclaimer_msg_txt, disclaimer_msg_html)

			self.replacebody(msg)

		self.log("eom reached", self.fromHeader) 

		return Milter.ACCEPT 


	def close(self):
		# always called, even when the abort is called, Clean up
		# any external resources here.
		return Milter.CONTINUE


	def abort(self):
		# client disconnected prematurely
		return Milter.CONTINUE


	# === Support Functions ===
	def log(self, *msg):
		t = (msg, self.id, time.time())
		if logq:
			logq.put(t)
		else:
			logmsg(*t)
			pass
	



def logmsg(msg,id,ts):
	print('{} [{}]'.format(time.strftime('%Y%b%d %H:%M:%S', time.localtime(ts)),id), end=None)
	for i in msg:
		print(i,end=None)
	print()
	sys.stdout.flush()


def background():
	while True:
		t = logq.get()
		if not t:
			break
		logmsg(*t)


def reformat_base64_message(email_object, disclaimer_msg, chunk=76):
	# Set padding for Disclaimer to prevent base64 structure break
	padding = 3 - (len(disclaimer_msg) % 3)
	disclaimer_msg += ' ' * padding
	disclaimer_msg = (base64.b64encode(disclaimer_msg.encode('utf-8'))).decode('utf-8')
	# Merge Disclaimer with main message
	new_email_content = disclaimer_msg + email_object.get_payload()
	# new_email_content = reformat_base64_message(new_email_content)

	new_email_content = ''.join(new_email_content.split('\n'))
	new_email_content = '\n'.join([new_email_content[i:i+chunk] for i in range(0,len(new_email_content),chunk)])
	return new_email_content


def embed_disclaimer(email_object, disclaimer_msg_txt, disclaimer_msg_html):
	for part in email_object.walk():
		if not part.is_multipart() and part.get_content_disposition() == None:		# Match single part message and message body (not attachment)
			content_type = part.get_content_type()
			transfer_encode = part.get("Content-Transfer-Encoding")

			if content_type == "text/plain":
				if transfer_encode == "base64":
					disclaimer_payload = reformat_base64_message(part, disclaimer_msg_txt)
				else:
					disclaimer_payload = disclaimer_msg_txt + part.get_payload()
				part.set_payload(disclaimer_payload)

			elif content_type == "text/html":
				if transfer_encode == "base64":
					disclaimer_payload = reformat_base64_message(part, disclaimer_msg_html)
				else:
					disclaimer_payload = disclaimer_msg_html + part.get_payload()
				part.set_payload(disclaimer_payload)
			else:
				print("[-] Unhandled mime type found: %s"%(content_type))

	if email_object.is_multipart():
		top_boundary = email_object.get_boundary()
		msg = str(email_object)
		start_index = msg.find(top_boundary)
		msg = msg[start_index:]
	else:
		email_object._headers.clear()
		msg = str(email_object)

	return msg




def main():
	bt = Thread(target=background)
	bt.start()
	socketname = "inet:%s@[127.0.0.1]"%(port_listen)
	timeout = 600
	# Register to have the Milter factory create instances of your class:
	Milter.factory = myMilter

	flags = Milter.CHGBODY + Milter.CHGHDRS + Milter.ADDHDRS + Milter.MODBODY
	Milter.set_flags(flags)
	
	print("%s milter startup" % time.strftime('%Y%b%d %H:%M:%S'))
	sys.stdout.flush()
	Milter.runmilter("pythonfilter",socketname,timeout)
	logq.put(None)
	bt.join()
	print("%s milter shutdown" % time.strftime('%Y%b%d %H:%M:%S'))


if __name__ == "__main__":
	# You probably do not need a logging process, but if you do, this
	# is one way to do it.
	logq = Queue(maxsize=4)
	main()
