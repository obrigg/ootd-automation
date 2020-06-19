import requests
import xmltodict
import time
from webexteamssdk import WebexTeamsAPI
from lxml import etree
from config import *
from collections import OrderedDict
from datetime import datetime

"""
The rules:
1. The word 'exit' in any given moment/input will abort and initialize the process.
2. There is a 5 minute timeout, without input the process will initialize.
3. 
"""

# Change to true to enable request/response debug output
DEBUG = False

# Custom exception for errors when sending requests
class SendRequestError(Exception):

    def __init__(self, result, reason):
        self.result = result
        self.reason = reason

    pass

def sendRequest( envelope ):
    if DEBUG:
        print( envelope )

    # Use the requests library to POST the XML envelope to the Webex API endpoint
    response = requests.post( 'https://api.webex.com/WBXService/XMLService', envelope )

    # Check for HTTP errors
    try: 
        response.raise_for_status()
    except requests.exceptions.HTTPError as err: 
        raise SendRequestError( 'HTTP ' + str(response.status_code), response.content.decode("utf-8") )

    # Use the lxml ElementTree object to parse the response XML
    message = etree.fromstring( response.content )

    if DEBUG:
        print( etree.tostring( message, pretty_print = True, encoding = 'unicode' ) )   

    # Use the find() method with an XPath to get the 'result' element's text
    # Note: {*} is pre-pended to each element name - ignores namespaces
    # If not SUCCESS...
    if message.find( '{*}header/{*}response/{*}result').text != 'SUCCESS':

        result = message.find( '{*}header/{*}response/{*}result').text
        reason = message.find( '{*}header/{*}response/{*}reason').text

        #...raise an exception containing the result and reason element content
        raise SendRequestError( result, reason )

    return message

def GetUserList():
    request = f'''<?xml version="1.0" encoding="UTF-8"?>
        <serv:message xmlns:serv="http://www.webex.com/schemas/2002/06/service"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <header>
                <securityContext>
                    <siteName>{SITENAME}</siteName>
                    <webExID>{WEBEXID}</webExID>
                    <password>{PASSWORD}</password>
                </securityContext>
            </header>
            <body>
	            <bodyContent xsi:type="java:com.webex.service.binding.user.LstsummaryUser">
                    <listControl>
                        <serv:startFrom>1</serv:startFrom>
                        <serv:maximumNum>500</serv:maximumNum>
                        <serv:listMethod>AND</serv:listMethod>
                    </listControl>
                        <order>
                            <orderBy>UID</orderBy>
                            <orderAD>ASC</orderAD>
                        </order>
                </bodyContent>
            </body>
        </serv:message>'''

    # Make the API request
    response = sendRequest( request )

    # Return an object containing the response
    return response

def ChangeUserName( webExId, firstName, lastName ):
    request = f'''<?xml version="1.0" encoding="UTF-8"?>
        <serv:message xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <header>
                <securityContext>
                    <siteName>{SITENAME}</siteName>
                    <webExID>{WEBEXID}</webExID>
                    <password>{PASSWORD}</password>
                </securityContext>
            </header>
            <body>
                <bodyContent xsi:type="java:com.webex.xmlapi.service.binding.user.SetUser">
                    <webExId>{webExId}</webExId>
                    <firstName>{firstName}</firstName>
                    <lastName>{lastName}</lastName>
                    <personalUrl>{firstName}{lastName}</personalUrl>
                    <personalMeetingRoom>
                        <title>{firstName} {lastName}'s virtual meeting place</title>
                    </personalMeetingRoom>
                </bodyContent>
            </body>
        </serv:message>'''

    # Make the API request
    response = sendRequest( request )

    # Return an object containing the response
    return response

def GetUserDetails( webExId ):
    request = f'''<?xml version="1.0" encoding="UTF-8"?>
        <serv:message xmlns:serv="http://www.webex.com/schemas/2002/06/service"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <header>
                <securityContext>
                    <siteName>{SITENAME}</siteName>
                    <webExID>{WEBEXID}</webExID>
                    <password>{PASSWORD}</password>
                </securityContext>
            </header>
            <body>
                <bodyContent xsi:type="java:com.webex.service.binding.user.GetUser">
                    <webExId>{webExId}</webExId>
                </bodyContent>
            </body>
        </serv:message>'''

    # Make the API request
    response = sendRequest( request )

    # Return an object containing the response
    return response

def FindTheRightRoom():
    # Get a list of rooms, and find the relevant room
    rooms = api.rooms.list()
    roomId = ""
    for room in rooms:
        if room.title == WEBEX_TEAMS_CONTACT:
            roomId = room.id
            break

    if roomId == "":
        print("ERROR!! The contact user/room: %s was not found" % WEBEX_TEAMS_CONTACT)
        raise Exception

    return (roomId)

def GetLastMessageReceived( roomId , botId ):
    # Get the latest message not by the bot
    try:
        messages = api.messages.list(roomId=roomId)
    except SendRequestError as err:
        print("Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
        print(err)
    for message in messages:
        if message.personId != botId:
            return message

def WaitForANewMessage( isInitialized , interval ):
    global lastMessage
    message = GetLastMessageReceived(roomId, botId)
    lastMessage = message # For the first run only, they are the same
    counter = 0
    while message.id == lastMessage.id:
        # Abort if over 20 attempts
        if (counter > 19) and not isInitialized:
            print("Counter reached 20... Aborting and starting over")
            api.messages.create(roomId=roomId,text="So... I've been waiting here for a while without any response...\nLet me start over, and we'll try again. Type anything to start.")
            raise Exception ('Counter reached 20... Aborting and starting over')
        counter = counter + 1
        print("No new messages... Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
        print("Going to sleep for %s seconds (counter: %s)" % (interval, (counter)))
        time.sleep(interval)        
        try:
            message = GetLastMessageReceived(roomId, botId)
        except:
            print ("An error has occured")
    if (message.text.lower() == "exit"):
            print("Received an EXIT or timed out. Aborting and starting from scratch")
            print("Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
            api.messages.create(roomId=roomId,text="Oooops... something has gone wrong if you typed 'exit'... Let me start over. Type anything to start.")
            raise Exception ('User entered "exit"')
    isInitialized = False
    return (message)

def NewMessageReceived ():
    # Whatever we received - we'll ask for a confirmation before creating a new room
    print("Confirming with the user that should start the process...")
    api.messages.create(roomId=roomId,text="Oh.. Hello! I didn't see you there...\nWould you like to create a new Webex Meetings room? (Y/N)")
    message = WaitForANewMessage ( isInitialized , 2 )
    
    if message.text.lower() == "y":
        print("User confirmed. Asking for a first name")
        api.messages.create(roomId=roomId,text="OK.. Let's get to work then!\nWhat is the first name?")
        message = WaitForANewMessage ( isInitialized , 2 )
        firstName = message.text
        print("Got first name, asking for the last name")
        api.messages.create(roomId=roomId,text="Got it.\nWhat is the last name?")
        message = WaitForANewMessage ( isInitialized , 2 )
        lastName = message.text
        print("Received last name. Let's get to work!")
        api.messages.create(roomId=roomId,text="Thanks!\nCrunching numbers...")
        designatedUser = FindAFreeUser()

        # Make the changes to the account
        try:
            response = ChangeUserName( designatedUser , firstName, lastName)
        except SendRequestError as err:
            print("Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
            print(err)
            raise SystemExit

        # Gather the details of the changed account
        try:
            response = GetUserDetails( designatedUser )
        except SendRequestError as err:
            print("Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
            print(err)
            raise SystemExit    
        
        response_dict = xmltodict.parse(etree.tostring( response, pretty_print = True, encoding = 'unicode' ))
        firstName = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:firstName']
        lastName = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:lastName']
        webExId = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:webExId']
        personalMeetingRoomURL = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:personalMeetingRoom']['use:personalMeetingRoomURL']
        accessCode = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:personalMeetingRoom']['use:accessCode']

        # Send a confirmation of the change
        message = f"""That's it. I'm done...  \nThe Webex space for **{firstName} {lastName}** is ready.  \nUsername: **{webExId}**  \nPersonal Meeting Room URL:  **{personalMeetingRoomURL}**  \nAccess Code: **{accessCode}**  \n - - - """
        api.messages.create(roomId=roomId,markdown=message)

def FindAFreeUser ():
    # Get the list of users
    try:
        response = GetUserList()
    except SendRequestError as err:
        print("Timestamp: %s" % datetime.now().strftime("%D %H:%M:%S"))
        print(err)
        raise SystemExit

    response_dict = xmltodict.parse(etree.tostring( response, pretty_print = True, encoding = 'unicode' ))
    users = response_dict['serv:message']['serv:body']['serv:bodyContent']['use:user']

    # Select a user called "family"
    freeUsers = OrderedDict()
    for user in users:
        if user['use:firstName'].lower() == "family":
            freeUsers.update(user)
    
    print("Selected user is: %s %s, email: %s " % (freeUsers['use:firstName'], freeUsers['use:lastName'], freeUsers['use:webExId']))
    api.messages.create(roomId=roomId,markdown="Selected user that will be **OVERWRITTEN** is: **%s %s**, email: **%s**.  \nIf you'd like to abort - type '**exit**', otherwise type '**ok**'" % (freeUsers['use:firstName'], freeUsers['use:lastName'], freeUsers['use:webExId']))
    message = WaitForANewMessage ( isInitialized , 2 )

    return(freeUsers['use:webExId'])

def mainLoop():
    while True:
        try:
            # Wait for a new message, then kick off the procedure
            global isInitialized
            isInitialized = True
            if (datetime.now().strftime("%H") in OFF_WORK_HOURS):
                print("Off work hours... Sleeping for 10 minutes")
                api.messages.create(roomId=roomId,text="Wow! looks at the time.. I'm going to off hours mode, checking in every 10 minutes.")
                WaitForANewMessage( isInitialized , 600 )
            else:
                WaitForANewMessage( isInitialized , 10 )
            isInitialized = False
            NewMessageReceived()
        except:
            print("An exception was raised - see previous notes")
            
# =================================================================

if __name__ == "__main__":
    # Initialize Webex Teams API
    api = WebexTeamsAPI(access_token=WEBEX_TEAMS_ACCESS_TOKEN)
    roomId = FindTheRightRoom()
    botId = api.people.me().id
    isInitialized = True

    print("Room ID: %s" % roomId)
    print("Bot ID: %s" % botId)
    print("I'm ready. Waiting for new messages..")

    mainLoop()
  