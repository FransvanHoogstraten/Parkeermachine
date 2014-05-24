DebuggingMode= 0 

LOG_FILENAME = "/var/log/bts_debug"

PortName="/dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if00-port0"
baudrate=115200
NOdevices=0
NOalarms=0

StatusUpdate = False													#This variable is not pickled, because we always start with a statusupdate (Cyclecounter = N)
FilterUpdate = False
DevStatUpdate = False
Scanning=True															#This variable is not pickled, because we always start in a Scanning mode


#init/default values. Only called on during initiation of machine (thereafter governed by cPickle)
timeout_sec = "300"
MinCount = "0"
highText="Hightext"
lowText="Lowtext"
WarTel="0"
UpdTel="0"				#correct values are extracted
FilterUpdTel="0"		#correct values are extracted
StatusWarned=False

#Filter1="FFFFFFFFFFFF"
Filter1="64:B9:E8:6A:27:75"
Filter2="FFFFFFFFFFFF"
Filter3="FFFFFFFFFFFF"
Filter4="FFFFFFFFFFFF"
Filter5="FFFFFFFFFFFF"

SMS=True
LED=True
BUZZER=True

Status_Update_DOLCD = True
GoToDefault=False
Pickle_WARNING_DOLCD=False
BT_Warning_DOLCD = False
GoToDefault_DOLCD = False
Filter_Update_DOLCD = False
New_SMS_DOLCD = False
Modem_DOLCD = False
High_Text_DOLCD = False
Low_Text_DOLCD = False
WarTel_DOLCD = False
Timeout_DOLCD = False
UI_DOLCD = False
Scanning_DOLCD = False
BT_Active_DOLCD = False
Alarms_DOLCD = False
Filter_all_DOLCD = False
CF_Cleared_DOLCD = False
CF_DOLCD = False
Reboot_DOLCD = False
Halt_DOLCD = False
DeepSettings_DOLCD = False
RestartCounter_DOLCD = False

#initialization
BT_activity_status=True
BT_hardware_check_status=True
Modem_hardware_check_status=True
AverMac = 0
nr_of_messages = 0
button_count = 0
rssi_old=0
rssi=0
reg_status="-"
reg_message="-"
operator="No GSM operator"
RestartCounter=0

classFilter=[]
