
#!/usr/bin/python
#

#import
import RPi.GPIO as GPIO
import time

# Define length of timeout, for beginning and end of strolling

timeout_scroll = 2			#This timeout only regulates the pauze before and after scrolling
timeout_main = 3			

# Define GPIO to LCD mapping
#LCD_RS = 4
#LCD_E  = 15
#LCD_D4 = 17 
#LCD_D5 = 18
#LCD_D6 = 22
#LCD_D7 = 23
#LED_ON = 24
# Define GPIO to LCD mapping
LCD_RS = 4
LCD_E  = 17
LCD_D4 = 18 
LCD_D5 = 22
LCD_D6 = 23
LCD_D7 = 24
LED_ON = 15

# Define some device constants
LCD_WIDTH = 16    # Maximum characters per line
LCD_CHR = True
LCD_CMD = False

LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line 

# Timing constants
E_PULSE = 0.00005
E_DELAY = 0.00005


def main(Upper, Lower):

	initial_text(Upper, Lower)
	upper_text(Upper)
	lower_text(Lower)
	


def initialize():
  # Main program block

  GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
  GPIO.setup(LCD_E, GPIO.OUT)  # E
  GPIO.setup(LCD_RS, GPIO.OUT) # RS
  GPIO.setup(LCD_D4, GPIO.OUT) # DB4
  GPIO.setup(LCD_D5, GPIO.OUT) # DB5
  GPIO.setup(LCD_D6, GPIO.OUT) # DB6
  GPIO.setup(LCD_D7, GPIO.OUT) # DB7
  GPIO.setup(LED_ON, GPIO.OUT) # Backlight enable

  # Initialise display
  lcd_init()
  time.sleep(0.2)	

def initial_text(Upper, Lower):

	GPIO.output(LED_ON, True)

	lcd_byte(LCD_LINE_1, LCD_CMD)
	lcd_string(Upper[0:15], 1)
	lcd_byte(LCD_LINE_2, LCD_CMD)
	lcd_string(Lower[0:15], 1)

def clear():

 	lcd_byte(LCD_LINE_1, LCD_CMD)
	lcd_string("                ", 1)
	lcd_byte(LCD_LINE_2, LCD_CMD)
	lcd_string("                ", 1)
	GPIO.output(LED_ON, False)

def upper_text(UpperString):

  if len(UpperString)<=16:

	lcd_byte(LCD_LINE_1, LCD_CMD)
	lcd_string(UpperString,1)
  else:
	scroll(LCD_LINE_1, timeout_scroll, UpperString)

def lower_text(LowerString):

  if len(LowerString)<=16:

	lcd_byte(LCD_LINE_2, LCD_CMD)
	lcd_string(LowerString,1)
  	time.sleep(timeout_main)
  else:
	scroll(LCD_LINE_2, timeout_scroll, LowerString)
	

def scroll(position, timeout, scroll_text):
  # This is where the strolling begins  
  for i in range (0, (len(scroll_text)-15)):
    lcd_byte(position, LCD_CMD)
    lcd_text = scroll_text[i:(i+16)]
    lcd_string(lcd_text,1)    
    if i==0:# and position==LCD_LINE_1:		#We only want the initial pauze for the upper line
	time.sleep(timeout)
    time.sleep(0.4)

  time.sleep(timeout)

  lcd_byte(position, LCD_CMD)
  lcd_string(scroll_text[0:15],1)


def lcd_init():
  # Initialise display
  lcd_byte(0x33,LCD_CMD)
  lcd_byte(0x32,LCD_CMD)
  lcd_byte(0x28,LCD_CMD)
  lcd_byte(0x0C,LCD_CMD)  
  lcd_byte(0x06,LCD_CMD)
  lcd_byte(0x01,LCD_CMD)  

def lcd_string(message,style):
  # Send string to display
  # style=1 Left justified
  # style=2 Centred
  # style=3 Right justified

  if style==1:
    message = message.ljust(LCD_WIDTH," ")  
  elif style==2:
    message = message.center(LCD_WIDTH," ")
  elif style==3:
    message = message.rjust(LCD_WIDTH," ")

  for i in range(LCD_WIDTH):
    lcd_byte(ord(message[i]),LCD_CHR)

def lcd_byte(bits, mode):
  # Send byte to data pins
  # bits = data
  # mode = True  for character
  #        False for command

  GPIO.output(LCD_RS, mode) # RS

  # High bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x10==0x10:
    GPIO.output(LCD_D4, True)
  if bits&0x20==0x20:
    GPIO.output(LCD_D5, True)
  if bits&0x40==0x40:
    GPIO.output(LCD_D6, True)
  if bits&0x80==0x80:
    GPIO.output(LCD_D7, True)

  # Toggle 'Enable' pin
  time.sleep(E_DELAY)    
  GPIO.output(LCD_E, True)  
  time.sleep(E_PULSE)
  GPIO.output(LCD_E, False)  
  time.sleep(E_DELAY)      

  # Low bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x01==0x01:
    GPIO.output(LCD_D4, True)
  if bits&0x02==0x02:
    GPIO.output(LCD_D5, True)
  if bits&0x04==0x04:
    GPIO.output(LCD_D6, True)
  if bits&0x08==0x08:
    GPIO.output(LCD_D7, True)

  # Toggle 'Enable' pin
  time.sleep(E_DELAY)    
  GPIO.output(LCD_E, True)  
  time.sleep(E_PULSE)
  GPIO.output(LCD_E, False)  
  time.sleep(E_DELAY)   

if __name__ == '__main__':

	Upper="Dit is denk ik net lang genoeg"
	Lower="OOK deze gaat scrollen"

#	Upper="kort"
#	Lower="korter"
	main(Upper, Lower)
