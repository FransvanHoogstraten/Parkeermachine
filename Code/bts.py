#!/usr/bin/env python

from __future__ import division
from datetime import datetime, timedelta
from variables import *
from subprocess import Popen, PIPE, STDOUT
import os, time, serial
import logging
import cPickle as pickle
import RPi.GPIO as GPIO
import threading, math
import LCD_scroller as LCD
import operator				#dit is om de tweede colom in de MinCountArray te kunnen aanroepen


# Logging initialization
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)

# GPIO mapping for UI devices
GPIO_Button_high=2
GPIO_Button_IN=3 
GPIO_Buzzer_grnd= 8
GPIO_Buzzer_sgnl= 7
GPIO_LED_grnd= 9
GPIO_LED_sgnl_1= 10
GPIO_LED_sgnl_2= 25

# Initializing GPIO ports
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)		
GPIO.setup(GPIO_Button_high,GPIO.OUT)
GPIO.setup(GPIO_Button_IN,GPIO.IN)
GPIO.setup(GPIO_Buzzer_grnd,GPIO.OUT)
GPIO.setup(GPIO_Buzzer_sgnl,GPIO.OUT)
GPIO.setup(GPIO_LED_grnd,GPIO.OUT)
GPIO.setup(GPIO_LED_sgnl_1,GPIO.OUT)
GPIO.setup(GPIO_LED_sgnl_2,GPIO.OUT)

# Initializing button HIGH contact 
GPIO.output(GPIO_Button_high, GPIO.LOW)

# Initializing LED ground contact
GPIO.output(GPIO_LED_grnd, GPIO.LOW)

# Initializing BUZZER ground contact
GPIO.output(GPIO_Buzzer_grnd, GPIO.LOW)

# Initialize m
m = 0

# Misc Initialization
array_of_filtered_devices = {}
MinCountArray = {}
time_last_BT_device = 0
bluetooth_alarm_counter=0					#variable to count the number of ERROR message of the bluetooth dongle
modem_alarm_counter=0
alarm = False

def hex2dec(mac):
	mac=mac.replace(":","") 
	dec = int(mac, 16)
	return dec
	
def messageInfo(messagetext):
	time=str(datetime.now())
	messagetext = time+" "+messagetext
	print messagetext
	logging.info(messagetext)

def messageWarning(messagetext):
	time=str(datetime.now())
	messagetext = time+" "+messagetext
	print messagetext
	logging.warning(messagetext)

def messageException(messagetext):
	time=str(datetime.now())
	messagetext = time+" "+messagetext
	print messagetext
	logging.exception(messagetext)

def messageError(messagetext):
	time=str(datetime.now())
	messagetext = time+" "+messagetext
	print messagetext
	logging.error(messagetext)

def get_uptime():
	try:
		with open('/proc/uptime', 'r') as f:
			uptime_seconds = float(f.readline().split()[0])
		
	except:
		messageException("Exception in get_uptime()")

	return uptime_seconds

def aver_mac(): 		
	global average_macs

	try:
		uptime_seconds=get_uptime()
		uptime_hours=int(uptime_seconds)/3600

		average_macs=int(NOdevices/uptime_hours)

	except:
		messageException("Exception in aver_mac()")

def BT_hardware_check():
	global Reboot_DOLCD, time_difference, time_last_BT_device

	time=get_uptime()	
	time_difference=int(time - time_last_BT_device)
	
def turn_off_check():
	if Scanning == False and StatusWarned == False:
		os.system("halt")
		time.sleep(300)			


def Modem_hardware_check():
	global Modem_hardware_check_status, modem_alarm_counter
	global rssi, rssi_old, reg_message, operator 
	try:
		ser.write("at+csq\r")
		rssi=ser.read(1000)
		rssi=rssi.split()[2]
		
		if rssi == 'ERROR:':			#This occurs when no SIM is present
			rssi='0'
		
		rssi=rssi.split(',')[0]
		rssi=rssi.replace(' ', '')

		if rssi=="99":					#This occurs when there is no connection
			rssi="0"
		else:
			rssi=int((int(rssi)/31)*100)


			rssi=int((rssi+rssi_old)/2)		#To average over last 2 cycles
			rssi_old=rssi


		messageInfo("GSM modem: Received Signal Strength Indication (RSSI): "+str(rssi)+"%")
		
		# Retrieve GSM operator name
		ser.write("at+creg?\r")

	        reg_status=ser.read(1000)

				
		#If no SIM present:
		if "SIM failure" in reg_status:
			messageWarning("Unable to retrieve GSM operator, SIM failure")
			operator="No SIM"
			return

		elif "COMMAND NOT SUPPORT" in reg_status:
			messageError("COMMAND NOT SUPPORT in response from modem, Modem_hardware_check()")

		reg_status=reg_status.split(",")[1]
		reg_status=reg_status.split("\r\n")[0]

		if reg_status=="0":
			reg_message="GSM modem: Not registered, not searching"
			Modem_hardware_check_status=False
		if reg_status=="1":
			reg_message="GSM modem: Registered to home network"
			Modem_hardware_check_status=True
		if reg_status=="2":
			reg_message="GSM modem: Not registered, searching for network"
			Modem_hardware_check_status=False
		if reg_status=="3":
			reg_message="GSM modem: Registration denied"
			Modem_hardware_check_status=False
		if reg_status=="5":
			reg_message="GSM modem: Registered, roaming"
			Modem_hardware_check_status=True

		if reg_status=="1" or reg_status=="5":
			ser.write("at+cops?\r")
			operator=ser.read(1000)

			try:
				operator=operator.split(",")[2]
				operator=operator.replace('"', '')
			except:
				messageException("Exception in reading GSM operator from modem")
		else:
			operator="No GSM operator"
			
		modem_alarm_counter=0

		if m % 25 ==0:
			messageInfo(reg_message)	
			messageInfo("GSM modem: connected to: "+operator)

	except:
		messageException("except in modem hardware check")		
		modem_alarm_counter=modem_alarm_counter+1
		resetPort()


	return Modem_hardware_check_status

def openPort():
	global ser, modem_alarm_counter
	try:
		ser=serial.Serial(PortName, baudrate, timeout=0.5)
		time.sleep(0.5)
		ser.write("at+cmgf=1\r")				#set text mode						
		r=ser.read(1000)
		ser.write("at+cops=0,1\r")				#set network operator readout mode	
		r=ser.read(1000)
		messageInfo("GSM modem port opened")
		
		modem_alarm_counter=0
		
	except:
		messageException("Exception in opening GSM modem port")
		modem_alarm_counter=modem_alarm_counter+1

def closePort():
	global ser
	try:
		ser.close()
		messageInfo("GSM modem port closed")
	except:
		messageException("Exception in closing GSM modem port")

def resetPort():																								
	global modem_alarm_counter	
	try:				
		openPort()
		time.sleep(2)
		ser.close()
		messageInfo("port closed")
		time.sleep(2)
		
		openPort()
		ser.write("\x1a")												#when the modem is resetted in the middle of sending process, it can get stuck there. This helps (Ctrl Z)
		r=ser.read(1000)
		ser.write("AT+CFUN=0\r")
		r=ser.read(1000)
		time.sleep(5)
		ser.write("AT+CFUN=1\r")
		r=ser.read(1000)
		time.sleep(5)
		
		messageInfo("port resetted")
		modem_alarm_counter=0
	except:
		messageException("Exception in resetting GSM modem port")
		modem_alarm_counter=modem_alarm_counter+1
		time.sleep(2)													#to stop the logs from filling up if bluetooth & modem dongels are both not connected

def pickle_load():
	global highText, lowText, UpdTel, WarTel, StatusWarned, timeout_sec
	global Filter1, Filter2, Filter3, Filter4, Filter5, classFilter
	global LED, BUZZER, SMS, GoToDefault, RestartCounter, Pickle_WARNING_DOLCD

##############Fundamentals###########	
	try:
		highText, lowText, UpdTel, WarTel, StatusWarned, timeout_sec = pickle.load(open("fundamentals_save_A.p", "rb"))
	except:
		messageException("Exception in pickle load of 'fundamentals_save_A.p'")
		#########Backup if file is corrupted###########
		try:
			highText, lowText, UpdTel, WarTel, StatusWarned, timeout_sec = pickle.load(open("fundamentals_save_B.p", "rb"))
		except:
			messageException("Exception in pickle load of 'fundamentals_save_B.p'")
			Pickle_WARNING_DOLCD=True

##############Filters###########	
	try:
		Filter1, Filter2, Filter3, Filter4, Filter5, classFilter = pickle.load(open("filter_save_A.p", "rb"))
	except:
		messageException("Exception in pickle load of 'filter_save_A.p'")
		#########Backup if file is corrupted###########
		try:
			Filter1, Filter2, Filter3, Filter4, Filter5, classFilter = pickle.load(open("filter_save_B.p", "rb"))
		except:
			messageException("Exception in pickle load of 'filter_save_B.p'")
			Pickle_WARNING_DOLCD=True

##############UIparameters###########	
	try:
		RestartCounter, SMS, LED, BUZZER, MinCount = pickle.load(open("UIparameters_save_A.p", "rb"))
	except:
		messageException("Exception in pickle load of 'UIparameters_save_A.p'")
		#########Backup if file is corrupted###########		
		try:
			RestartCounter, SMS, LED, BUZZER, MinCount = pickle.load(open("UIparameters_save_B.p", "rb"))
		except:
			messageException("Exception in pickle load of 'UIparameters_save_B.p'")
			Pickle_WARNING_DOLCD=True
		
##############Go To Default###########	
	if GoToDefault==True:
		from variables import highText, lowText, UpdTel, WarTel, timeout_sec
		from variables import Filter1, Filter2, Filter3, Filter4, Filter5, classFilter
		from variables import RestartCounter, LED, BUZZER, SMS, MinCount
		
		GoToDefault=False
		messageInfo("GoToDefault ==> ALL VARIABLES RESET TO DEFAULT")

		
def pickle_dump_A():
	try: 
		pickle.dump([highText, lowText, UpdTel, WarTel, StatusWarned, timeout_sec], open("fundamentals_save_A.p", "wb"))		
	except:
		messageException("Exception during pickle dump of 'fundamentals_save_A.p'")
	try:	
		pickle.dump([Filter1, Filter2, Filter3, Filter4, Filter5, classFilter], open("filter_save_A.p", "wb"))
	except:
		messageException("Exception during pickle dump of 'filter_save_A.p'")
	try:	
		pickle.dump([RestartCounter, SMS, LED, BUZZER, MinCount], open("UIparameters_save_A.p", "wb"))	
	except:
		messageException("Exception during pickle dump of 'UIparameters_save_A.p'")	
		
def pickle_dump_B():
	try: 
		pickle.dump([highText, lowText, UpdTel, WarTel, StatusWarned, timeout_sec], open("fundamentals_save_B.p", "wb"))		
	except:
		messageException("Exception during pickle dump of 'fundamentals_save_B.p'")
	try:	
		pickle.dump([Filter1, Filter2, Filter3, Filter4, Filter5, classFilter], open("filter_save_B.p", "wb"))
	except:
		messageException("Exception during pickle dump of 'filter_save_B.p'")
	try:	
		pickle.dump([RestartCounter, SMS, LED, BUZZER, MinCount], open("UIparameters_save_B.p", "wb"))	
	except:
		messageException("Exception during pickle dump of 'UIparameters_save_B.p'")	
	
		
		
def log_variables():
	try:

		messageInfo("current value of 'HighText' is "+highText)
		messageInfo("current value of 'LowText' is "+lowText)
		messageInfo("current value of 'UpdTel' is "+UpdTel)				#Kunnen deze niet weg?
		messageInfo("current value of 'FilterUpdTel' is "+FilterUpdTel)		#Kunnen deze niet weg?
		messageInfo("current value of 'Telnr' is "+WarTel)
		messageInfo("current value of 'Timeout' is "+str(timeout_sec))
		messageInfo("current value of 'Scanning' is "+str(Scanning))
		messageInfo("current value of 'MACs Checked' is "+str(NOdevices))
		messageInfo("current value of 'AverMAC' is "+str(average_macs))
		messageInfo("current value of 'Last' is: "+str(time_difference))
		messageInfo("current value of 'Alarms' is "+str(NOalarms))
		messageInfo("current value of 'WarActive' is "+str(StatusWarned))
		messageInfo("current value of 'LED' is "+str(LED))
		messageInfo("current value of 'Buzzer' is "+str(BUZZER))
		messageInfo("current value of 'SMS' is "+str(SMS))
		messageInfo("current value of 'F1' is "+Filter1)
		messageInfo("current value of 'F2' is "+Filter2)
		messageInfo("current value of 'F3' is "+Filter3)
		messageInfo("current value of 'F4' is "+Filter4)
		messageInfo("current value of 'F5' is "+Filter5)
		messageInfo("current value of 'CF' is "+str(classFilter))
		messageInfo("current value of 'RestartCounter' is "+str(RestartCounter))
		messageInfo("current value of 'MinCount' is "+str(MinCount))
		
	except:
		messageException("Exception while logging variables")

def wildcard2limits(inp):
	try:
		inp=inp.split("*")[0]
		inp=inp.replace(":", "")	
		low=inp.ljust(12, '0')
		high=inp.ljust(12, 'F')
		output=low+"==="+high
	
	except:
		messageException("Exception during wildcard2limits()")
	
	return output
			
def createMAClimits():													
	global lowFilter1, highFilter1, lowFilter2, highFilter2, lowFilter3
	global highFilter3, lowFilter4, highFilter4, lowFilter5, highFilter5 
	
	try:
		temp=wildcard2limits(Filter1)
		lowFilter1=temp.split("===")[0]
		highFilter1=temp.split("===")[1]
	
		temp=wildcard2limits(Filter2)
		lowFilter2=temp.split("===")[0]
		highFilter2=temp.split("===")[1]
	
		temp=wildcard2limits(Filter3)
		lowFilter3=temp.split("===")[0]
		highFilter3=temp.split("===")[1]
	
		temp=wildcard2limits(Filter4)
		lowFilter4=temp.split("===")[0]
		highFilter4=temp.split("===")[1]
	
		temp=wildcard2limits(Filter5)
		lowFilter5=temp.split("===")[0]
		highFilter5=temp.split("===")[1]
		
	except:
		messageException("Exception during createMAClimits()")
		
def extract_date_time(header_message):
	try:
		dateSMS=header_message.split(",")[3]
		dateSMS=dateSMS[1:]
		dateSMS=dateSMS.replace("/", "-")
		timeSMS=header_message.split(",")[4]
		timeSMS=timeSMS.split("+")[0]
		
		messageInfo("date extracted from message: "+dateSMS)
		messageInfo("time extracted from message: "+timeSMS)
		
		if StatusWarned==False:									#If updating is allowed when alarm is on, problems with timing may occur
			os.system('date -s %s' % dateSMS)
			os.system('date -s %s' % timeSMS)
			messageInfo("System Time set from message time  ")
		else:
			messageWarning("System Time was not adjusted, because alarm is now active")
		
	except:
		messageException("Exception in extract_date_time()")

def extract_telnr(header_message):

	try:
		telnrSMS=header_message.split(",")[1]
		telnrSMS=telnrSMS.replace('"', "")
		messageInfo("telnr extracted from message: "+telnrSMS)

	except:
		messageException("Exception in extract_telnr")

	return telnrSMS
	
def modem_BT_alarm():
	global alarm, RestartCounter

	if bluetooth_alarm_counter > 0:
		alarm = True
		if bluetooth_alarm_counter > 3:
			messageError("Bluetooth Error: Going for Reboot")
			time.sleep(20)
			os.system("reboot")
			RestartCounter += 1
			time.sleep(300)					#to enable future login and to give pickle enough time to load
	else:
		alarm = False
	
	if modem_alarm_counter > 0:
		alarm = True
		if modem_alarm_counter > 3:
			messageError("Modem Error: Going for Reboot")
			time.sleep(20)
			os.system("reboot")
			RestartCounter += 1
			time.sleep(300)					#to enable future login and to give pickle enough time to load
	else:
		alarm = False

	
def find_mac_addresses(): 		
	global Reboot_DOLCD, bluetooth_alarm_counter
	
	try:
		all_macs = []
		command = Popen('hcitool inquire --flush --numrsp=50',shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True) #--length
		output = command.stdout.read()
		error = command.stderr.read()

		error=str(error)
	
		if len(error) != 0:
			messageError("BT dongle returns error: "+error)
			bluetooth_alarm_counter=bluetooth_alarm_counter+1			

		else:
			bluetooth_alarm_counter=0

		output=str(output)
		output=output.replace("Inquiring ...\n","")
		output=output.replace("\t", "")
		output=output.split("\n")
		output=filter(None, output)			#remove empty string at the end

		for response in output:
			mac = response.split("clock")[0]
			bt_class = response.split("class: ")[1] 
			bt_class = bt_class.split("\n")[0]
			all_macs.append(mac+"="+bt_class)
			messageInfo(mac+"       "+bt_class)
			
	except:
		messageException("Exception during find_mac_addresses()")
													
    
	return all_macs														

	
def scan():
	global all_macs, NOalarms
	global NOdevices, time_last_BT_device

	try:
		all_macs = find_mac_addresses()
		time = datetime.now()

		for entry in all_macs:

			time_last_BT_device = get_uptime()	
			mac=entry.split("=")[0]
			bt_class=entry.split("=")[1]
			
			NOdevices = NOdevices + 1
			
			if (hex2dec(mac) >= hex2dec(lowFilter1) and hex2dec(mac) <= hex2dec(highFilter1)) or \
			(hex2dec(mac) >= hex2dec(lowFilter2) and hex2dec(mac) <= hex2dec(highFilter2)) or \
			(hex2dec(mac) >= hex2dec(lowFilter3) and hex2dec(mac) <= hex2dec(highFilter3)) or \
			(hex2dec(mac) >= hex2dec(lowFilter4) and hex2dec(mac) <= hex2dec(highFilter4)) or \
			(hex2dec(mac) >= hex2dec(lowFilter5) and hex2dec(mac) <= hex2dec(highFilter5)):
				

				if len(classFilter)==0 or bt_class in classFilter:
				
					if not array_of_filtered_devices.has_key(mac):
							
						if len(classFilter)==0:
							messageInfo("Class filter has not been set")
						else:
							messageInfo("Class filter contents: " + str(classFilter))
			

						messageInfo("ENTER: " + mac + "       with class: " + bt_class)
						MinCountArray[mac] = 0

						if len(array_of_filtered_devices)==0:			#So that only one alarm will be counted if two Triggerdevices are sight.
							NOalarms = NOalarms + 1

					else:
						pass
						
					array_of_filtered_devices[mac] = time
					MinCountArray[mac] = MinCountArray[mac] + 1
					messageInfo("MinCountArray for " + str(mac) + " is set to " + str(MinCountArray[mac]))

				else:
					messageWarning("MAC filter match, but no class match: " + mac + "       with class: " + bt_class)
	except:
		messageException("Exception during scan()")
	
def timeout_check():
	try:
		time = datetime.now()
		devices_to_delete = []

		for device in array_of_filtered_devices:
			time_ls = array_of_filtered_devices[device]
			
			if Scanning == True:
				
				if (time - time_ls).seconds > int(timeout_sec):
					devices_to_delete.append(device)
					messageInfo("EXIT: " + device)
				
			elif Scanning == False:
				
				messageInfo("Scanning = False")
				devices_to_delete.append(device)
				messageInfo("Scanning turned to False ==> EXIT: " + device)
		

		for deldevice in devices_to_delete:
			del array_of_filtered_devices[deldevice]
			del MinCountArray[deldevice]
	except:
		messageException("Exception during timeout_check()")
			
			
def sendPeriodicalSMS():
	global StatusWarned
	global StatusUpdate, FilterUpdate, DevStatUpdate

	try:
		if SMS==True:
			if StatusWarned==False and len(array_of_filtered_devices)!=0 and (max(MinCountArray.iteritems())[1]>=int(MinCount)):
				status=sendSMS(highText, highText, WarTel)
				if status==True:
					StatusWarned=True
			
			elif StatusWarned==True and len(array_of_filtered_devices)==0:
				status=sendSMS(lowText, lowText, WarTel)
				if status==True:
					StatusWarned=False
					
			else:
				pass	


		if StatusUpdate == True:
			
			StatusUpdateText=\
			"H="+highText+"\r\n"+\
			"L="+lowText+"\r\n"+\
			"Telnr="+WarTel+"\r\n"+\
			"Timeout="+str(timeout_sec)+"\r\n"+\
			"MinCount="+str(MinCount)+"\r\n"+\
			"\r\n"+\
			"Scanning="+str(Scanning)+"\r\n"+\
			"Alarms="+str(NOalarms)+"\r\n"+\
			"LED/Buzzer/SMS="+str(LED)+"/"+str(BUZZER)+"/"+str(SMS)+"\r\n"+\
			"GSM= "+operator+" ("+str(rssi)+"%)"
			
															
			
			status=sendSMS("Status Update", StatusUpdateText, UpdTel)
			if status==True:
				StatusUpdate=False
		
		if FilterUpdate==True:
			
			stringC=str(classFilter)
			stringC=stringC.replace("[","")
			stringC=stringC.replace("]","")
			
			
			FilterUpdateText=\
			"MAC filters: \r\n"+\
			"F1="+Filter1+"\r\n"+\
			"F2="+Filter2+"\r\n"+\
			"F3="+Filter3+"\r\n"+\
			"F4="+Filter4+"\r\n"+\
			"F5="+Filter5+"\r\n"+\
			"\r\n"+\
			"Class Filters: \r\n"+\
			"CF="+stringC
			
			
			status=sendSMS("Filter Update", FilterUpdateText, FilterUpdTel)
			if status==True:
				FilterUpdate=False
		
		if DevStatUpdate==True:
						
			
			DevStatUpdateText=\
			"AverMac= "+str(average_macs)+"\r\n"+\
			"Last (sec): "+str(time_difference)+"\r\n"+\
			"RestCount= "+str(RestartCounter)
			
			
			status=sendSMS("DevStat Update", DevStatUpdateText, UpdTel)
			if status==True:
				DevStatUpdate=False
		
	except:
		messageException("Exception during sendPeriodicalSMS()")
	
def split_len(seq, length):
	return [seq[i:i+length] for i in range(0, len(seq), length)]
	
def sendSMS(descrText, smsText, smsTel):
	try:
		MessageSent=False

		sms_ingekort=smsText.replace("\r", "")
		length=len(sms_ingekort)
		messageInfo("Number of characters in SMS (max 150): "+str(length))							#for safety reasons we use maximum of 150 characters
		NOmessages=int(math.ceil(length/150))
		messageInfo("Number of messages needed: "+str(NOmessages))

		sms_array=split_len(smsText, 150)

		x=1
		force_break=False						#to make sure that we don't get stuck in the loop when trying to send an sms.

		while x <= NOmessages and force_break==False:
			messageInfo("sending message "+str(x)+" of "+str(NOmessages))
		
			try:
				messageInfo("SMS attempt: \"" + descrText + "\" to " + smsTel)
			
				try:
					ser.write("AT+CMGS=\"" + smsTel + "\"\r")
					time.sleep(0.5)
					ser.write(sms_array[x-1])
					time.sleep(0.5)
					ser.write("\x1a")
				except:
					MessageSent=False
					messageException("Exception in sendSMS(), writing to modem")
					resetPort()						
					
				
				maxim=0

				while True: 
					
					maxim=maxim+1			
					try:
						ret=ser.read(1000)						#Delete the \n from this string, then write it to messageInfo
					except:						
						messageException("Exception in sendSMS(), reading from modem")
						resetPort()

					#If no SIM present:
					if "SIM failure" in ret:
						messageWarning("Unable to send SMS, SIM failure")
						resetPort()
						return
											

					elif "COMMAND NOT SUPPORT" in ret:
						messageError("COMMAND NOT SUPPORT in response from modem, sendSMS()")

					# Hier nog een registratie van een 'general "error" response' inbouwen, eerst op RPi even checken hoe dit er uit ziet.
						
					elif "+CMGS:" in ret and "OK" in ret:
						
						messageInfo("SMS "+str(x)+" of "+str(NOmessages)+" sent")
						if x==NOmessages:
							MessageSent=True
							messageInfo("all messages sent")
						x=x+1
						break
					
					elif maxim>100:			
						messageError("Maximum allowed modem timeout reached, sms sending FAILED")					#do we need a maximum of 10 tries? AT commands seem to be stored in modem memory when NO CARRIER
						force_break=True
						break
				
				
			except:
				MessageSent=False
				messageException("Exception during sendSMS(), inner try-loop")
				resetPort()
	except:
		messageException("Exception during sendSMS()")
	
	
	return MessageSent



def receiveSMS():
	global ser
	global StatusUpdate, FilterUpdate, DevStatUpdate
	global highText, lowText, WarTel, UpdTel, FilterUpdTel, timeout_sec, Scanning
	global Filter1, Filter2, Filter3, Filter4, Filter5, classFilter
	global SMS, LED, BUZZER, GoToDefault, nr_of_messages, MinCount
	global m,k 
	global New_SMS_DOLCD, High_Text_DOLCD, Low_Text_DOLCD, WarTel_DOLCD, UpdTel_DOLCD, Timeout_DOLCD, UI_DOLCD, Scanning_DOLCD
	global Filter_all_DOLCD, CF_Cleared_DOLCD, CF_DOLCD, Reboot_DOLCD, Halt_DOLCD, Status_Update_DOLCD, Filter_Update_DOLCD, GoToDefault_DOLCD
	
	
	try:
		nr_of_messages=0						#initialization (because of option of SIM failure)
		ser.write("AT+CPMS=\"SM\"\r")
		ret=ser.read(1000)
		
		#If no SIM present:
		if "SIM failure" in ret:
			messageWarning("Unable to check for new SMS, SIM failure")
		
		elif "COMMAND NOT SUPPORT" in ret:
			messageError("COMMAND NOT SUPPORT in response from modem, receiveSMS()")
			resetPort()
		
		else:
			#Check how many new messages there are
			split=ret.split("+CPMS: ")[1]
			nr_of_messages=int(split.split(",")[0])
			messageInfo("Number of new messages: "+str(nr_of_messages))
		
		#Read memory banks only if there are new messages
		
		sms_read=0													#number of messages correctly read
		sms_mem_bank=0													#memory bank currently being investigated
		
		while sms_read < nr_of_messages:
			messageInfo("Now checking memory bank "+str(sms_mem_bank))
			ser.write("AT+CMGR="+str(sms_mem_bank)+"\r")
			ret=ser.read(100000)

			if ret.endswith("OK\r\n"):
				ret_check=ret.split("\n")[1]
				if ret_check.startswith("+CMGR:"):
					
					extract_date_time(ret_check)
					TelTemp = extract_telnr(ret_check)
					
					messageInfo("NEW sms in Memory Bank "+str(sms_mem_bank))

					New_SMS_DOLCD=True
					

					n=1														#each modem response starts with a \n
					
					try:
						while True:
							try:
								line=ret.split("\n")[n]					#Has its own try loop, because this is the only except that is normal
							except:
								messageException("Exception caused by end of SMS. No action required")
								break
								
							messageInfo("line "+str(n)+": "+ line)	#log the content of each received message
							
							
							
							if line.startswith("H="):						#Set Trigger-High warning
								line=line.split("\r")[0]
								highText = line.split("=")[1]
								messageInfo("hightext is set to " + highText)
								High_Text_DOLCD=True
								
							elif line.startswith("L="):						#Set Trigger-Low warning
								line=line.split("\r")[0]
								lowText = line.split("=")[1]
								messageInfo("lowtext is set to " + lowText)
								Low_Text_DOLCD=True
								
							elif line.startswith("Telnr="):				#Set Warning Telephone number
								line=line.split("\r")[0]
								WarTel = line.split("=")[1]
								messageInfo("SMS Telnumber is set to " + WarTel)
								WarTel_DOLCD=True
																					
							elif line.startswith("Timeout="):				#Set Timeout
								line=line.split("\r")[0]
								timeout_sec = line.split("=")[1]
								messageInfo("Timeout is set to " + timeout_sec)
								Timeout_DOLCD=True

							elif line.startswith("MinCount="):				#Set MinCount
								line=line.split("\r")[0]
								MinCount = line.split("=")[1]
								messageInfo("MinCount is set to " + MinCount)
								Timeout_DOLCD=True

							elif line.startswith("!LED!"):
								if LED==True:
									LED=False
									messageInfo("LED User Interface is set to False")
								else:
									LED=True
									messageInfo("LED User Interface is set to True")

								UI_DOLCD=True

							elif line.startswith("!Buzzer!"):
								if BUZZER==True:
									BUZZER=False
									messageInfo("BUZZER User Interface is set to False")
									
								else:
									BUZZER=True
									messageInfo("BUZZER User Interface is set to True")
									tripple_blink_Buzzer()

								UI_DOLCD = True

							elif line.startswith("!SMS!"):
								if SMS==True:
									SMS=False
									messageInfo("SMS User Interface is set to False")
									
								else:
									SMS=True
									messageInfo("SMS User Interface is set to True")

								UI_DOLCD = True


					
							elif line.startswith("Scanning"):				#This toggles Start/Stop
								if Scanning == True:
									Scanning = False
									messageInfo("Scanning is set to False")
								else:
									Scanning = True	
									messageInfo("Scanning is set to True")
									
								Scanning_DOLCD = True
	
									
									
							elif line.startswith("F1="):				#Set F1
								line=line.split("\r")[0]
								Filter1 = line.split("=")[1]
								messageInfo("MAC Filter 1 is set to " + Filter1)
								Filter_all_DOLCD = True
							elif line.startswith("F2="):				#Set F2
								line=line.split("\r")[0]
								Filter2 = line.split("=")[1]
								messageInfo("MAC Filter 2 is set to " + Filter2)
								Filter_all_DOLCD = True
							elif line.startswith("F3="):				#Set F3
								line=line.split("\r")[0]
								Filter3 = line.split("=")[1]
								messageInfo("MAC Filter 3 is set to " + Filter3)
								Filter_all_DOLCD = True
							elif line.startswith("F4="):				#Set F4
								line=line.split("\r")[0]
								Filter4 = line.split("=")[1]
								messageInfo("MAC Filter 4 is set to " + Filter4)
								Filter_all_DOLCD = True
							elif line.startswith("F5="):				#Set F5
								line=line.split("\r")[0]
								Filter5 = line.split("=")[1]
								messageInfo("MAC Filter 5 is set to " + Filter5)
								Filter_all_DOLCD = True
								
							elif line.startswith("CF=Clear"):			#Clearing Class Filter
								classFilter=[]
								messageInfo("Class Filter has been cleared")
								CF_Cleared_DOLCD = True

							
							elif line.startswith("CF="):				#Adding to Class Filter
								classFilter=[]
								line=line.split("\r")[0]
								class_string = line.split("=")[1]
								
								class_position=0
								while True:
					
									added_class = class_string.split(",")[class_position]
									added_class = added_class.replace("'", "")  
									added_class = added_class.replace(" ", "")
									classFilter.append(added_class)
									messageInfo(added_class + " has been added to the class filter")

									class_position=class_position + 1
									
									CF_DOLCD = True	
									
							elif line.startswith("Reboot") :			#Remotely rebooting
								messageInfo("System Reboot commanded by user")
								Reboot_DOLCD=True				#actual rebooting done in LCD thread
								os.system("reboot")


							elif line.startswith("Halt"):				#Remotely halting
								messageInfo("System Halt commanded by user")
								Halt_DOLCD = True				#actual halting done in LCD thread
								os.system("halt")
							
									
								
							elif line.startswith("Update"):
								StatusUpdate=True
								messageInfo("StatusUpdate is set to True")
								UpdTel=TelTemp
								messageInfo("UpdTel is set to "+UpdTel)	
							
							elif line.startswith("FilterUpdate"):
								FilterUpdate=True
								messageInfo("MacFilterUpdate is set to True")
								FilterUpdTel=TelTemp
								messageInfo("FilterUpdTel is set to "+FilterUpdTel)	

							elif line.startswith("DevStatUpdate"):
								DevStatUpdate=True
								messageInfo("DevStatUpdate is set to True")
								UpdTel=TelTemp
								messageInfo("UpdTel is set to "+UpdTel)	
							
							elif line.startswith("GoToDefault"):
								GoToDefault=True
								messageInfo("GoToDefault set to True")
								GoToDefault_DOLCD = True
							n=n+1
							
							
					except:
						messageException("Exception in receiveSMS(), reading SMS")
			
				
					ser.write("AT+CMGD="+str(sms_mem_bank)+"\r")					
					ret=ser.read(1000)
					messageInfo("message in memory bank "+str(sms_mem_bank)+" deleted")
				
					sms_read = sms_read + 1
					messageInfo("number of messages read in this cycle:"+str(sms_read))
					sms_mem_bank=sms_mem_bank + 1
					if sms_mem_bank>=25:
						break
					
				else: 
					messageInfo("no message in memory bank "+ str(sms_mem_bank))
					sms_mem_bank=sms_mem_bank + 1
					if sms_mem_bank>=25:
						break
			
			else:
				messageWarning("no correct modem response while reading memory bank "+str(sms_mem_bank))
				resetPort()
				break
			
	except:
		messageException("Exception during receiveSMS()")
		resetPort()


def check_button():
	global Status_Update_DOLCD, Filter_Update_DOLCD, Scanning, Scanning_DOLCD, button_count, DeepSettings_DOLCD

	try:
		if button_count==100:
			DeepSettings_DOLCD = True

		elif button_count==10:
			if Scanning == True:
				Scanning = False
				messageInfo("Scanning is set to False")
			else:
				Scanning = True	
				messageInfo("Scanning is set to True")
					
			Scanning_DOLCD = True

		elif button_count>=5 and button_count<22 and GPIO.input(GPIO_Button_IN):
			Filter_Update_DOLCD = True


		elif button_count>0 and button_count<5 and GPIO.input(GPIO_Button_IN):
			Status_Update_DOLCD = True

		# checking the button
		if not GPIO.input(GPIO_Button_IN):
			messageInfo("BUTTON COUNT: "+str(button_count))
			button_count = button_count + 1
		

		else:
			button_count=0
	except:
		messageException("Exception during check_button()")

def blink_LED():
	try:
		# set correct 'color variable'
		if len(array_of_filtered_devices)!=0 and (max(MinCountArray.iteritems())[1]>=int(MinCount)):
			Y_Active=GPIO_LED_sgnl_1
			N_Active=GPIO_LED_sgnl_2
		else:
			Y_Active=GPIO_LED_sgnl_2
			N_Active=GPIO_LED_sgnl_1

		# Activating LED
		if LED==True:
			if Scanning ==	True:
				GPIO.output(Y_Active, GPIO.HIGH)
				GPIO.output(N_Active, GPIO.LOW)
				
			else:											#making LED blink when Scanning = False
				GPIO.output(Y_Active, GPIO.HIGH)
				GPIO.output(N_Active, GPIO.LOW)
				time.sleep(0.2)
				GPIO.output(Y_Active, GPIO.LOW)
				GPIO.output(N_Active, GPIO.LOW)
		else:
			GPIO.output(GPIO_LED_sgnl_1, GPIO.LOW)
			GPIO.output(GPIO_LED_sgnl_2, GPIO.LOW)
			
	except:
		messageException("Exception during blink_LED")

def blink_Buzzer(force):	
	try:
		# Blinking the Buzzer
		if (len(array_of_filtered_devices)!=0 and (max(MinCountArray.iteritems())[1]>=int(MinCount))) or force=="force":
			if BUZZER==True:
				GPIO.output(GPIO_Buzzer_sgnl, GPIO.HIGH)
				time.sleep(0.2)
				GPIO.output(GPIO_Buzzer_sgnl, GPIO.LOW)
		else:
			GPIO.output(GPIO_Buzzer_sgnl, GPIO.LOW)
	except:
		messageException("Exception during blink_Buzzer()")

def tripple_blink_Buzzer():
	try:
		blink_Buzzer("force")
		time.sleep(0.3)
		blink_Buzzer("force")
		time.sleep(0.3)
		blink_Buzzer("force")
	except:
		messageException("Exception during tripple_blink_Buzzer()")




	
def scan_thread():
	global m
	while True:
		try:
			messageInfo("*** 2 THREAD SCANNING ***")
			aver_mac()
			BT_hardware_check()
			turn_off_check()
			modem_BT_alarm()
			createMAClimits()
			if Scanning==True:
				scan()
			else:
				time.sleep(2)
			timeout_check()  
			
			if m % 200 ==0:
				log_variables()
				m = 1				#to prevent m from going to infinity
			
			m = m + 1

		except:
			messageException("Exception in scan_thread(), inside while-loop")

def message_thread():
	temp=0
	while True:
		try:
			pickle_load()			#This should always be first in this Thread!!!!

############################ START BODY THREAD ####################

			if temp % 10 ==0:				#Is this once every 10 seconds?
				Modem_hardware_check()
			if temp % 30 ==0:
				messageInfo("*** 1 THREAD MESSAGE ***")
				temp=0

			receiveSMS()
			time.sleep(2)
			sendPeriodicalSMS()
			temp += 1

############################ END BODY THREAD ####################

			pickle_dump_A()			#This should always be last in this Thread!!!!
			time.sleep(0.1)
			pickle_dump_B()			#This should always be last in this Thread!!!!
		except:
			messageException("Exception in message_thread(), inside while-loop")

		
def polling_thread():
	# Initialization sequence
	try:
		temp = 0
	except:
		messageException("Exception during polling_thread(), initialization sequence")

	while True:
		try:
			check_button()
			time.sleep(0.1)

			temp=temp+1

			if temp % 200 == 0:
				messageInfo("*** 3 THREAD POLLING ***")
				temp = 0
		except:
			messageException("Exception in polling_thread(), inside while-loop")
			
def display_thread():
	global New_SMS_DOLCD, High_Text_DOLCD, Low_Text_DOLCD, WarTel_DOLCD, UpdTel_DOLCD, Timeout_DOLCD, UI_DOLCD, Scanning_DOLCD, BT_Active_DOLCD, Modem_DOLCD, DeepSettings_DOLCD, RestartCounter_DOLCD
	global Filter_all_DOLCD, CF_Cleared_DOLCD, CF_DOLCD, Reboot_DOLCD, Halt_DOLCD, Status_Update_DOLCD, Filter_Update_DOLCD, GoToDefault_DOLCD, MinCount_DOLCD, Pickle_WARNING_DOLCD

	# Initialization sequence
	try:
		LCD.initialize()
		LCD.main("BTSMS-LCD  V1.0", "** Booting... **")
		temp = 0
	except:
		messageExcept("Exception in display_thread(), initialization sequence")

	while True:
		try:
			
		# Factory default
			if GoToDefault_DOLCD==True:
				LCD.initialize()
				LCD.main("    FACTORY     ", "     RESET     ")			 #hier moeten later alle losse variabelen methods worden aangeroepen
				Status_Update_DOLCD=True
				Filter_Update_DOLCD=True

				GoToDefault_DOLCD=False

		# Verzamelcommando's:
			if Status_Update_DOLCD==True:
				LCD.initialize()
				LCD.main(" STATUS UPDATE:","****************")			 #hier moeten later alle los	se variabelen methods worden aangeroepen
				Scanning_DOLCD = True
				Modem_DOLCD = True
				High_Text_DOLCD = True
				Low_Text_DOLCD = True
				WarTel_DOLCD = True
				UpdTel_DOLCD = True
				UI_DOLCD = True
	

				Status_Update_DOLCD=False

		#Warnings
			if Pickle_WARNING_DOLCD==True:
				LCD.initialize()
				LCD.main("     ERROR", "LOADING SETTINGS" )
				Pickle_WARNING_DOLCD=False

		#Losse commandos
			if New_SMS_DOLCD==True:
				LCD.initialize()
				LCD.main(" New Messages: "+str(nr_of_messages), "****************" )
				New_SMS_DOLCD=False

			if Modem_DOLCD==True:
				LCD.initialize()
				LCD.main("Oper.: "+operator,"Signal: "+str(rssi)+"%")
				Modem_DOLCD=False

			if Scanning_DOLCD==True:
				LCD.initialize()
				LCD.main("Scanning= "+str(Scanning),"Nr of Alarms= "+str(NOalarms))
				Scanning_DOLCD=False

			if High_Text_DOLCD==True:
				LCD.initialize()
				LCD.main("High SMS (H)=", highText)
				High_Text_DOLCD=False

			if Low_Text_DOLCD==True:
				LCD.initialize()
				LCD.main("Low SMS (L)=", lowText)
				Low_Text_DOLCD=False

			if WarTel_DOLCD==True:
				LCD.initialize()
				LCD.main("Telnr=", str(WarTel))
				WarTel_DOLCD=False

			if UI_DOLCD==True:
				LCD.initialize()
				LCD.main("LED/Buzzer/SMS=",  str(LED)+"/"+str(BUZZER)+"/"+str(SMS))
				UI_DOLCD=False




		#Verzamelcommando
			if Filter_Update_DOLCD==True:
				LCD.initialize()
				LCD.main("FILTER SETTINGS:", "****************")			 #hier moeten later alle losse variabelen methods worden aangeroepen
				Filter_all_DOLCD = True
				CF_DOLCD = True
				Timeout_DOLCD = True

				Filter_Update_DOLCD=False



		#Losse commandos
			if Filter_all_DOLCD==True:
				LCD.initialize()
				LCD.main("Filter 1 (F1)=", Filter1)
				LCD.main("Filter 2 (F2)=", Filter2)
				LCD.main("Filter 3 (F3)=", Filter3)
				LCD.main("Filter 4 (F4)=", Filter4)
				LCD.main("Filter 5 (F5)=", Filter5)
				Filter_all_DOLCD=False

			if CF_Cleared_DOLCD==True:
				LCD.initialize()
				LCD.main("  Class Filter  ", "    Cleared    ")
				CF_Cleared_DOLCD=False

			if CF_DOLCD==True:
				LCD.initialize()
				LCD.main("Class Filter=", str(classFilter))
				CF_DOLCD=False
			
			if Timeout_DOLCD==True:
				LCD.initialize()
				LCD.main("Timeout= " + str(timeout_sec), "MinCount= " + MinCount)
				Timeout_DOLCD=False

			if Reboot_DOLCD==True:
				LCD.initialize()
				messageError("System going down for Reboot")
				LCD.main("   Rebooting", "****************")
				Reboot_DOLCD==False

			if Halt_DOLCD==True:
				LCD.initialize()
				LCD.main("System Shutdown", "****************")
				Halt_DOLCD==False

				
		#Verzamelcommando
			if DeepSettings_DOLCD==True:
				LCD.initialize()
				LCD.main("DEV. STATISTICS:", "****************")			 #hier moeten later alle losse variabelen methods worden aangeroepen
				BT_Active_DOLCD = True
				RestartCounter_DOLCD = True

				DeepSettings_DOLCD=False



		#Losse commandos
			if BT_Active_DOLCD==True:
				LCD.initialize()
				LCD.main("AverMac= "+str(average_macs), "Last (sec): "+str(time_difference))
				BT_Active_DOLCD=False

			if RestartCounter_DOLCD==True:
				LCD.initialize()
				LCD.main("RestCount= "+str(RestartCounter), "")
				RestartCounter_DOLCD=False
				

			LCD.clear()
			time.sleep(0.5)					#to reduce the continuous looping
		


			temp=temp+1

			if temp % 20 == 0:
				messageInfo("*** 4 THREAD DISPLAY ***")
				temp = 0

		except:
			messageException("Exception in display_thread(), inside while loop")
			time.sleep(0.5)

def blink_thread():
	#Initialization sequence
	try:
		tripple_blink_Buzzer()
		temp = 0
	except:
		messageException("Exception during blink_thread(), initialization sequence")
		
	while True:
		try:
			#FAST BLINKING IN CASE OF ALARM
			if alarm == True:
				GPIO.output(GPIO_LED_sgnl_1, GPIO.HIGH)
				GPIO.output(GPIO_LED_sgnl_2, GPIO.LOW)
				time.sleep(0.1)
				GPIO.output(GPIO_LED_sgnl_1, GPIO.LOW)
				GPIO.output(GPIO_LED_sgnl_2, GPIO.LOW)
				time.sleep(0.1)

			else:
				blink_LED()
				blink_Buzzer("")
				time.sleep(0.5)

				temp=temp+1

				if temp % 20 == 0:
					messageInfo("*** 5 THREAD BLINK ***")
					temp=0
					
		except:
			messageException("Exception during blink_thread(), inside while-loop")



if __name__ == '__main__':
	try:
		messageInfo("program start")
		openPort()

		u=threading.Thread(target=message_thread)			#aangezien de pickle-load in deze thread zit, moet deze als eerste
		v=threading.Thread(target=scan_thread)
		w=threading.Thread(target=polling_thread)
#		x=threading.Thread(target=display_thread)
		y=threading.Thread(target=blink_thread)
		u.start()
		v.start()
		w.start()
#		x.start()
		y.start()
	except:
		messageException("Exception during __main__")
