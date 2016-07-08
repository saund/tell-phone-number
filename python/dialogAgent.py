#!/usr/bin/python -tt

#dialogAgent.py is for an Agent model for a dialog management system to
#transmit structured data between a transmitter and a receiver using 
#natural, human-like conversational dialogue.
#
#A DialogAgent holds two DialogModels.  One DialogModel represents their
#own state of belief, while the other represents their state of belief about
#their conversation partner.   (In the future this framework might support
#3-way conversations and more.)
#
#A DialogModel holds belief state consisting of belief about the topic 
#of the dialogue (the DataModel), plus additional belief related to dialog
#management such as readiness, turn, and data communication protocol.
#




import csv
import random
import sys
import copy
import re
import os
import os.path
import platform
import math
import thread
import time
import getpass
from os.path import expanduser
import ruleProcessing as rp
from gtts import gTTS

#for playing a wav file
import pyaudio
import wave

#import speech_recognition as sr
#Using a modified version of the speech_recognition library __init__.py file
#to give us the ability to abort out of listening.
import speech_recognition_tpn as sr




#Test just the rules in isolated-rules-test.txt
def loopDialogTest():
    rp.initLFRules('isolated-rules-test.txt')
    loopDialogMain()


#The DialogAgent representing the computer conversation participant.
gl_agent = None
#gl_turn_history = []   defined below

#This is set by use_debug_mode of loopDialog function
gl_use_wait_timer_p = True

def setUseWaitTimer(val):
    global gl_use_wait_timer_p
    gl_use_wait_timer_p = val


#This is set by use_debug_mode of loopDialog function
gl_use_speech_p = True

def setUseSpeech(val):
    global gl_use_speech_p
    gl_use_speech_p = val



    
#Reset state by creating a new agent and clearing the turn history.
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopDialog(use_debug_mode=False):
    global gl_agent
    global gl_turn_history
    global gl_turn_number
    global gl_time_tick_ms
    global gl_use_wait_timer_p
    global gl_use_speech_p
    if use_debug_mode:
        gl_use_speech_p = False
        gl_use_wait_timer_p = False  
    else:
        gl_use_speech_p = True
        gl_use_wait_timer_p = True

    gl_agent = createBasicAgent()
    gl_turn_history = []  
    gl_turn_number = 0
    gl_pending_question_list = []
    rp.initLFRulesIfNecessary()
    if gl_use_wait_timer_p:
        createAndStartWaitTimer(gl_time_tick_ms)
    if gl_use_speech_p:
        initializeASR(gl_energy_threshold)
        startNewSpeechRecRunner()

    #rp.setTell(True)
    setTranscriptFilepath()
    openTranscriptFile()

    da_issue_dialog_invitation = generateDialogInvitation('send-receive')
    da_generated_word_list = rp.generateTextFromDialogAct(da_issue_dialog_invitation)
    print 'da_generated_word_list: ' + str(da_generated_word_list)

    gl_turn_history.insert(0, (gl_turn_number, 'self', [da_issue_dialog_invitation], da_generated_word_list))
    gl_turn_number += 1
    str_da_invitation = da_issue_dialog_invitation.getPrintString()
    #allow "yes" and "no"
    possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,\
                                               gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure,\
                                               gl_da_receive, gl_da_send)
    removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
    pushQuestionToPendingQuestionList(gl_turn_number, 'self', gl_da_request_dm_invitation_send_receive, 
                                      str_da_invitation, (possible_answers_to_invitation_question))


    if da_generated_word_list != None:
        str_generated = ' '.join(da_generated_word_list)
        print 'gen: ' + str_generated

        if gl_use_speech_p and len(str_generated) > 0:
            ttsSpeakText(str_generated)
            resetCurrentTurnBeliefs()

        writeToTranscriptFile('Output: ' + str_generated)
    
    loopDialogMain()


#a list of tuples of incoming Dialog Acts.  Each tuple is of the form,
#  (originator, dialog_act_list)
#Most of the time this will be empty.  The keyboard input, wait timeout,
#and ASR threads all place things on the end.  The loop takes things off the front
gl_dialog_act_queue = []

gl_stop_main_loop = False

def stopMainLoop():
    global gl_stop_main_loop
    print 'stopMainLoop setting gl_stop_main_loop to True'
    gl_stop_main_loop = True


#To deal with the multiple input modalities, this uses a polling strategy.
#The first version had a while loop that blocked on keyboard input.
#Then, wait timeout and ASR ran on separate threads.  But wait timeout has
#to be reset after TTS, and TTS has to shut off ASR so the ASR doesn't respond
#to TTS utterances.  This all got very complicated and the different threads were 
#tripping over themselves.
#
#So the new strategy is that the main loop takes things off an input queue.  The various
#threads are able to add to the queue independently.
#Not sure if thread locks will be necessary.  Probably the queue should be locked
#by anyone modifying it.
def loopDialogMain():
    global gl_dialog_act_queue
    global gl_stop_main_loop
    global gl_agent

    gl_stop_main_loop = False
    startKeyboardInputThread()
    gl_dialog_act_queue = []



    while gl_stop_main_loop == False:
        time.sleep(.01)     #run at 100Hz
        #time.sleep(2.0)     #run at 100Hz
        #print ' in main loop, gl_stop_main_loop: ' + str(gl_stop_main_loop)

        if len(gl_dialog_act_queue) > 0:
            
            da_item = gl_dialog_act_queue[0]
            gl_dialog_act_queue = gl_dialog_act_queue[1:]

            da_list = da_item[1]
            print '\nhandling input from ' + da_item[0] + ' ' + str(len(da_list)) + ' das:'
            for da in da_list:
                print '    ' + da.getPrintString()
            print ' '
            (response_da_list, turn_topic) = generateResponseToInputDialog(da_list)

            #print 'got ' + str(len(da_list)) + ' DialogActs'
            #print 'raw: ' + str(da_list)
            print 'response_da_list: ' + str(len(response_da_list))
            output_word_list = []
            for da in response_da_list:
                #print 'intent:' + da.intent
                #print 'arg_list: ' + str(da.arg_list)
                da.printSelf()
                da_generated_word_list = rp.generateTextFromDialogAct(da)
                if da_generated_word_list == None:
                    print 'could not generate a string from da'
                else:
                    output_word_list.extend(da_generated_word_list)
                #print 'lfs: ' + str(da.arg_list)
                #for lf in da.arg_list:
                #    lf.printSelf()

            #printAgentBeliefs(False)
            str_generated = ' '.join(output_word_list)
            print 'gen: ' + str_generated

            if gl_use_speech_p and len(str_generated) > 0:
                ttsSpeakText(str_generated)
                resetCurrentTurnBeliefs()

            writeToTranscriptFile('Output: ' + str_generated)

            #print '\nInput:'
            sys.stdout.write('Input: ')
            sys.stdout.flush()
        
    stopKeyboardInputThread()
    stopTimer()
    stopSpeechRunner()
    closeTranscriptFile()
    


def startKeyboardInputThread():
    thread.start_new_thread(keyboardInputThreadFunction, (keyboard_input_callback_function,))

gl_keyboard_input_running_p = False

def stopKeyboardInputThread():
    global gl_keyboard_input_running_p
    print 'stopKeyboardInputThread()'
    gl_keyboard_input_running_p = False

def keyboardInputThreadFunction(keyboard_input_callback_function):
    global gl_keyboard_input_running_p
    gl_keyboard_input_running_p = True

    print 'keyboard input started'
    while gl_keyboard_input_running_p:
        input_string = raw_input('\nKInput: ')
        input_string = rp.removePunctuationAndLowerTextCasing(input_string)

        print '///////////////////////////////////'
        print '//  ' + str(input_string)
        print '///////////////////////////////////'
        #print 'keyboard sees: ' + input_string
        writeToTranscriptFile('Input: ' + input_string)

        if input_string == 'quit':
            print 'quit seen, calling stopMainLoop()'
            stopMainLoop()
            gl_keyboard_input_running_p = False

        rule_match_list = rp.applyLFRulesToString(input_string)
        if rule_match_list == False:
            print 'no DialogRule matches found'
        else:
            print 'MATCH: ' + str(rule_match_list);
            da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)
        keyboard_input_callback_function(da_list)

    print 'keyboard input stopped'


def keyboard_input_callback_function(da_list):
    global gl_dialog_act_queue
    gl_dialog_act_queue.append(('Keyboard', da_list))

    






#Treat speech input the same as typed input
def handleSpeechInput(input_string):
    global gl_dialog_act_queue

    writeToTranscriptFile('Input: ' + input_string)
    input_string = rp.removePunctuationAndLowerTextCasing(input_string)

    print 'handleSpeechInput: '
    print '///////////////////////////////////'
    print '//   ' + str(input_string)
    print '///////////////////////////////////'


    rule_match_list = rp.applyLFRulesToString(input_string)
    if rule_match_list == False:
        print 'no DialogRule matches found'
    else:
        print 'MATCH: ' + str(rule_match_list);
    da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)

    if len(da_list) > 0:
        gl_dialog_act_queue.append(('Speech', da_list))




#self_or_partner is 'self' or 'partner'
#Returns a tuple of the last turn on the part of self or partner:
#  (turn_number, speaker = 'self' or 'partner', DialogAct list, utterance word tuple)
#target_intent_list is a list of target intents that must be present in at least one 
#utterance of the turn in order to return that turn, i.e. one of:
# { InformTopicInfo, InformTopicManagement, RequestTopicInfo,RequestDialogManagement, 
#   CheckTopicInfo, CheckDialogManagement, ConfirmTopicInfo, ConfirmDialogManagement,
#   CorrectionTopicInfo, CorrectionDialogManagemnt}
#Or, target_intent_list can be 'any'
def fetchLastUtteranceFromTurnHistory(self_or_partner, target_intent_list='any'):
    global gl_turn_history
    for item_tup in gl_turn_history:
        if item_tup[1] == self_or_partner:
            if target_intent_list == 'any':
                return item_tup
            for da in item_tup[2]:
                if da.intent in target_intent_list:
                    return item_tup
    return None


def printTurnHistory():
    global gl_turn_history
    print '\nTurn History:'
    for turn_tup in gl_turn_history:
        turn_number = turn_tup[0]
        speaker = turn_tup[1]
        da_list = turn_tup[2]
        utterance_text = getTextForDialogActList(da_list)
        print str(turn_number) + ' ' + speaker + ' da_list (below): ' + utterance_text
        for da in da_list:
            print '    ' + da.getPrintString()
    print ' '
            




#Returns da_list with the first DialogAct removed if it is fits with the spec_arg
#
# spec_arg can be:
#   'confirmation-or-correction'
#   'sorry'
#This is used if the agent says,
# "no the area code is six five zero" 
#and the user asks to repeat that. Don't repeat the initial, "no"
def possiblyStripLeadingDialogAct(da_list, spec_arg):
    if len(da_list) < 1:
        return da_list
    da0 = da_list[0]
    str_da0 = da0.getPrintString()

    if spec_arg == 'confirmation-or-correction' and \
       str_da0 == 'CorrectionTopicInfo(negation)' or \
       str_da0 == 'CorrectionDialogManagement(negation)' or \
       str_da0 == 'ConfirmDialogManagement(affirmation-yes)' or \
       str_da0 == 'CorrectionTopicInfo(negation-polite)':
        return da_list[1:]

    if spec_arg == 'sorry' and \
       str_da0 == gl_str_da_inform_dm_self_correction:
        return da_list[1:]
    return da_list




#return da_list with any DialogActs removed that match the str_da in str_da_filter_list
def stripDialogActsOfType(da_list, str_da_filter_list):
    ok_da_list = []
    for da in da_list:
        str_da = da.getPrintString()
        okay_p = True
        for filter_str_da in str_da_filter_list:
            print ' stripDialogActsOfType ' + str_da + ' filter: ' + filter_str_da
            if str_da.find(filter_str_da) >= 0:
                okay_p = False
                break
        if okay_p:
            ok_da_list.append(da)
    print 'strip returning ' + str(len(ok_da_list))
    for da in ok_da_list:
        print '   ' + da.getPrintString()
    return ok_da_list





    


#Remember who the current turn belongs to so that the turn beliefs may be reset after
#TTS output has finished speaking or while ASR is collecting ongoing speech.
#This essentially resets the wait timer for when self decides that their turn belief 
#exceeds threshold because they thought it was partner's turn but partner hasn't taken it.
gl_current_turn_holder = 'either'

def resetCurrentTurnBeliefs():
    global gl_agent
    gl_agent.setTurn(gl_current_turn_holder)




#Returns an Agent that is either a sender ('send') or receiver ('receive') of a telephone number
#that should be ready to engage in dialogue.
def createBasicAgent():
    agent = DialogAgent()
    agent.name = 'computer'
    agent.partner_name = 'person'
    #These get set when the agent determines to either send or receive a phone number
    #agent.send_receive_role = send_or_receive
    #agent.self_dialog_model = initDialogModel('self', send_or_receive)
    #agent.partner_dialog_model = initDialogModel('partner', sendReceiveOpposite(send_or_receive))
    return agent




def sendReceiveOpposite(send_or_receive):
    if send_or_receive == 'send':
        return 'receive'
    elif send_or_receive == 'receive':
        return 'send'
    else:
        print 'sendReceiveOpposite() got invalid arg ' + send_or_receive
        return None



#The semantics of a model of self and partner's beliefs, represented as distributions.
#
#self_dialog_model holds the self participant's belief in the data values and the dialog parameters.
#Is this a distribution?  Could be, if self is uncertain about the data values.
#
#partner dialog model has a confounding of possible interpretations.
#Is it, 
#  A. self's belief distribution about what partner holds as categorical values?
#  B. self's certain assertion of knowledge of what belief distribution partner holds?
#  C. self's belief distribution about what partner holds as a distribution over values?
#     In this case, it's a distribution of distributions.
#
#There is a fundamental difference in belief about facts and belief about aspects of
#dialog status that are socially negotiated.
#
#The values of digits are objective facts.  
#For the party holding the digit values, each digit's value is categorical, not a distribution.
#For the receiving party if the digit values are a distribution, then we'll have to use
#interpretations B or C.   Maybe with C, the distribution of distributions can be collapased
#into a single distribution.
#Alternatively, we can assume the receiver has a categorical belief in each digit value
#(which could be 'unknown').  
#Then, interpretation A comes into play. The distribution is self's distribution of 
#belief over which categorical value of digit value partner holds.
#Uncertainty will lead A to call for confirmation.
#
#Objective values are subject to belief recursion: "I believe that you believe that...".
#But even in the more complex case of C, there is always some grounded belief distrubution 
#across data values.
#
#By contrast, index pointer and turn are socially negotiated.
#Socially negotiated values are espcially difficult to disentagle from belief recursion 
#because there is no grounding in data values.  The only objective grounding is what was
#physically said.  But what was physically said is not what people care about. What they
#care about was the meaning of what was said, which is a reference to belief states.
#But this is itself subject to interpretation--and to differing 
#interpretations of the meanings inferred by eacy party.   So instead of recusion built
#from solid ground, we have recursion in a swirl of interpretations of interpretations.
#
#You get situations like,
#"You said X which I interpreted as X' but then I said Y and I thought you agreed to Y"
#
#Maybe this is the solution.  For socially negotiated properties, we *pretend* that there
#is an objective value written down somewhere.  Each party maintains its belief in what
#that value is, based on all past interaction.  That belief is a distribution over
#possible values of the objective value.  
#For turn, the value options might be  self / either / partner
#so the distribution is a multinomial.  During active conversation, the model
#might be that the objective value assigns turn to 'self' or 'partner' (but not 'either'),
#and that each participant estimates what the relative distribution is between
#them.  With wait time, the estimate slides toward oneseself, i.e. self's belief slides
#toward it believing it is self's turn, partner belief slides toward believing
#it is partner's turn.  So eventually someone is prompted to speak.
#Whereas, when the data exchange has concluded, then turn belief sloshes 
#into 'either'
#
#With data index pointer, the pretend objective value is the index of the digit or other
#data value being communicated.  Between communication of data values, this property's 
#value can linger around to reflect expectation of what data index's value will be 
#communicated next.



class DialogAgent():
    def __init__(self):
        self.name = None
        self.partner_name = None
        #for now, role serves as goal/activity status
        self.self_dialog_model = None
        self.partner_dialog_model = None
        self.setRole('banter')                 #initialize with 'banter' role


    #If the role is send, then the DialogAgent will be initialized with a send_phone_number which will
    #be stuffed into the self_dialog_model.  The DialogAgent will be initialized believing that the 
    #recipient has no information about the phone number.
    #If the role is receive, then the send_phone_number will be None and the communction partner 
    #will be responsible for obtaining the phone number they speak to the DialogAgent, 
    #and the DialogAgent will start off with no information about the phone number.
    def setRole(self, send_or_receive, send_phone_number=None):
        self.send_receive_role = send_or_receive
        if send_or_receive == 'banter':
            self.self_dialog_model = initBanterDialogModel('self', self.self_dialog_model)
            self.partner_dialog_model = initBanterDialogModel('partner', self.partner_dialog_model) 
            return None
        #phone number will only be used by the sending DialogModel
        self.self_dialog_model = initSendReceiveDataDialogModel('self', send_or_receive, send_phone_number, self.self_dialog_model)
        self.partner_dialog_model = initSendReceiveDataDialogModel('partner', sendReceiveOpposite(send_or_receive), None, self.partner_dialog_model)
        return None

    #turn_value can be 'self', 'either', 'partner'
    #this is from the point of view of the DialogAgent, which in this program will be the computer agent
    def setTurn(self, turn_value):
        global gl_current_turn_holder
        gl_current_turn_holder = turn_value
        self.self_dialog_model.turn.setAllConfidenceInOne(turn_value)
        self.partner_dialog_model.turn.setAllConfidenceInOne(turn_value)

    def adjustTurnTowardSelf(self, delta):
        self.self_dialog_model.adjustTurnTowardSelf(delta)
        self.partner_dialog_model.adjustTurnTowardSelf(delta)   #toward absolute self, not toward partner to agent.self

    #control_owner can be 'self', 'either', 'partner'
    #this is from the point of view of the DialogAgent, which in this program will be the computer agent
    def setControl(self, control_owner):
        self.self_dialog_model.control.setAllConfidenceInOne(control_owner)
        self.partner_dialog_model.control.setAllConfidenceInOne(control_owner)

    def getCurrentControl(self):
        return self.self_dialog_model.control.getDominantValue()
        
    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = 'DialogAgent: ' + self.name
        pstr += '     partner: ' + self.partner_name + '\n'
        pstr += 'role: ' + self.send_receive_role + '\n\n'
        pstr += self.self_dialog_model.getPrintString() + '\n'
        pstr += self.partner_dialog_model.getPrintString() + '\n'
        return pstr

    #def getConsensusIndexPointer(self, tell=False):
    #    self_dom_value = self.self_dialog_model.data_index_pointer.getDominantValue()
    #    partner_dom_value = self.partner_dialog_model.data_index_pointer.getDominantValue()
    #    if tell:
    #    print 'getConsensusIndexPointer  self: ' + str(self_dom_value) + ' partner: ' + str(partner_dom_value)
    #    if self_dom_value == partner_dom_value:
    #        return self_dom_value
    #    else:
    #        return None


    

#There will be one DialogModel for owner=self and one for owner=other-speaker
class DialogModel():
    def __init__(self, previous_dialog_model=None):
        self.model_for = None       #one of 'self', 'partner'
        
        #for this application...
        self.data_model = None                   #A DataModel_USPhoneNumber

        #This is being obsoleted 2016/06/25
        #self.data_index_pointer = None           #An OrderedMultinomialBelief: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
                                                 #data_index_pointer is self's belief about which data item is being referred to.
                                                 #Ontologically, we use the "pretend objective" strategy, where we pretend that
                                                 #there is an objective state of data_index_pointer, and the distribution is over
                                                 #beliefs in the value of that state on the part of self and partner.
                                                 #For an agent's self_dialog_model, index_pointer is used to look up data values to send,
                                                 #normally when agent's partner_dialog_model's index_pointer is in agreement.
                                                 #For an agent's partner_dialog_model, index_pointer can indicate either of two things:
                                                 #  -1. which digit the partner is referring to when they confirm data values
                                                 #  -2. which digit the partner is expecting to receive when self sends more data

        if previous_dialog_model != None:        #carry over the turn_topic_list from previous roles for this speaker
            self.turn_topic_list = previous_dialog_model.turn_topic_list
        else:
            self.turn_topic_list = []            # A list of TurnTopic instances

        #should be generic for all data communication applications
        self.readiness = None                    #A BooleanBelief: 1 = ready, 0 = not
        self.turn = None                         #An OrderedMultinomialBelief: ['self', 'either', 'partner'] 
                                                 # turn value is absolute not relative to the dialog model. 
                                                 # So turn = 'self' always means the turn belongs to the agent.self speaker,
                                                 # regardless of whether the dialog model is self_dialog_model or partner_dialog_model.
        self.control = None                      #An OrderedMultinomialBelief: ['self', 'either', 'partner']
                                                 #Control goes to partner if they ask a question, then reverts to self when they
                                                 #relinquish it.
        self.protocol_chunck_size = None         #An OrderedMultinomialBelief: [1, 2, 3, 10]
        self.protocol_handshaking = None         #An OrderedMultinomialBelief: [1, 2, 3, 4, 5]  1 = never, 5 = every turn


    #who is one of 'self', 'either', 'partner'
    def getTurnConfidence(self, who):
        return self.turn.getValueConfidence(who)

    def adjustTurnTowardSelf(self, delta):
        self_conf = self.turn.getValueConfidence('self')
        new_self_conf = max(0.0, min(1.0, self_conf + delta))
        self.turn.setValueConfidenceNormalizeOthers('self', new_self_conf)

    #new_control_owner is one of 'self', 'either', 'partner'
    def setControlTo(self, new_control_owner):
        self.control.setValueConfidenceNormalizeOthers(new_control_owner, 1.0)

    def getWhoHasControl(self):
        return self.control.getDominantValue()

    def addTurnTopic(self, turn_topic):
        self.turn_topic_list.append(turn_topic)

    def getLastTurnTopic(self):
        return self.turn_topic_list[len(self.turn_topic_list)-1]

    def printTurnTopics(self):
        for turn_topic in self.turn_topic_list:
            turn_topic.printSelf()

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = 'DialogModel for ' + self.model_for + '\n'
        pstr += 'data_model_abbrev: ' + self.data_model.getPrintStringAbbrev() + '\n'
        pstr += 'data_model: ' + self.data_model.getPrintString() + '\n'
        #pstr += 'data_index_pointer: ' + self.data_index_pointer.getPrintString() + '\n'
        pstr += 'readiness: ' + self.readiness.getPrintString() + '\n'
        pstr += 'turn: ' + self.turn.getPrintString() + '\n'
        pstr += 'chunk_size: ' + self.protocol_chunk_size.getPrintString() + '\n'
        pstr += 'handshaking: ' + self.protocol_handshaking.getPrintString() + '\n'
        return pstr



gl_default_phone_number = '6506371212'

def initSendReceiveDataDialogModel(self_or_partner, send_or_receive, send_phone_number=None, previous_dialog_model=None):
    global gl_default_phone_number
    global gl_10_digit_index_list
    global gl_turn_mnb
    global gl_control_mnb
    global gl_chunk_size_mnb
    global gl_handshake_level_mnb
    dm = DialogModel(previous_dialog_model)
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    if send_or_receive == 'send' and send_phone_number != None:
        dm.data_model.setPhoneNumber(send_phone_number)
    #dm.data_index_pointer = OrderedMultinomialBelief(gl_10_digit_index_list)
    #dm.data_index_pointer.setAllConfidenceInOne(0)                      #initialize starting at the first digit
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief(gl_turn_mnb)
    dm.turn.setAllConfidenceInOne('either')                             #will get overridden
    dm.control = OrderedMultinomialBelief(gl_control_mnb)
    dm.control.setAllConfidenceInOne('either')                          #will get overridden
    dm.protocol_chunk_size = OrderedMultinomialBelief(gl_chunk_size_mnb)
    dm.protocol_chunk_size.setAllConfidenceInTwo(3, 4)                  #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief(gl_handshake_level_mnb)
    dm.protocol_handshaking.setAllConfidenceInOne(3)                    #initialize with moderate handshaking
    return dm


def initBanterDialogModel(self_or_partner, previous_dialog_model=None):
    global gl_default_phone_number
    dm = DialogModel(previous_dialog_model)
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    #dm.data_index_pointer = OrderedMultinomialBelief(gl_10_digit_index_list)
    #dm.data_index_pointer.setEquallyDistributed()                       #no index pointer
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief(gl_turn_mnb)
    dm.turn.setAllConfidenceInOne('either')
    dm.control = OrderedMultinomialBelief(gl_control_mnb)
    dm.control.setAllConfidenceInOne('either')                          #will get overridden
    dm.protocol_chunk_size = OrderedMultinomialBelief(gl_chunk_size_mnb)
    dm.protocol_chunk_size.setAllConfidenceInTwo(3, 4)                 #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief(gl_handshake_level_mnb)
    dm.protocol_handshaking.setAllConfidenceInOne(3)                   #initialize with moderate handshaking
    return dm



        



class DataModel():
    def __init__(self):
        self.data_type = None       #e.g. 'us-phone-number'
        self.owner = None
        self.data_beliefs = None     



class DataModel_USPhoneNumber(DataModel):
    def __init__(self):
        self.type = 'us-phone-number'
        self.data_beliefs = [DigitBelief(), DigitBelief(), DigitBelief(),\
                             DigitBelief(), DigitBelief(), DigitBelief(),\
                             DigitBelief(), DigitBelief(), DigitBelief(), DigitBelief()]
        #data segments, [start_index, end_index] inclusive
        self.data_indices = {'area-code':[0,2],\
                             'exchange':[3,5],\
                             'line-number':[6,9],\
                             'telephone-number':[0,9]}


    #phone_number_string is like '3452233487', i.e. ten digits in a row
    def setPhoneNumber(self, phone_number_string):
        if phone_number_string != None and len(phone_number_string) != 10:
            print 'setPhoneNumber got a phone_number_string: ' + phone_number_string + ' that is not 10 digits long'
            return
        for i in range(0, 10):
            numerical_digit = phone_number_string[i]
            word_digit = numericalDigitToWordDigit(numerical_digit)
            self.data_beliefs[i].setValueDefinite(word_digit)


    #digit_value is a string
    def setNthPhoneNumberDigit(self, nth, digit_value, prob=1.0):
        self.data_beliefs[nth].setValueProb(digit_value, prob)
        #self.data_beliefs[nth].setValueDefinite(digit_value)

    def resetUnknownDigitValues(self):
        for digit_i in range(0, 10):
            self.data_beliefs[digit_i].setValueUnknown()

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = '( ' + self.data_beliefs[0].getPrintString() + ' '\
                    + self.data_beliefs[1].getPrintString() + ' '\
                    + self.data_beliefs[2].getPrintString() + ' ) '\
                    + self.data_beliefs[3].getPrintString() + ' '\
                    + self.data_beliefs[4].getPrintString() + ' '\
                    + self.data_beliefs[5].getPrintString() + ' - '\
                    + self.data_beliefs[6].getPrintString() + ' '\
                    + self.data_beliefs[7].getPrintString() + ' '\
                    + self.data_beliefs[8].getPrintString() + ' '\
                    + self.data_beliefs[9].getPrintString() + ' )'
        return pstr

    def getPrintStringAbbrev(self):
        pstr = '( ' + self.data_beliefs[0].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[1].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[2].getPrintStringAbbrev() + ' ) ' +\
                      self.data_beliefs[3].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[4].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[5].getPrintStringAbbrev() + ' - ' +\
                      self.data_beliefs[6].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[7].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[8].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[9].getPrintStringAbbrev()
        return pstr



gl_telephone_number_field_names = ['area-code', 'exchange', 'line-number', 'country-code', 'extension']





#For telephone number communication, the Banter data model will hold conversation
#context state about
# -user and agent goals and intentions
#  (user or agent intent to send or receive a phone number)
# -agent competency
# -maybe something about the various phone numbers the agent knows, to
#  enrich the selection. Make it more like a directory.
class DataModel_Banter(DataModel):
    def __init__(self):
        self.type = 'banter'
        self.current_topic = None

    def getPrintString(self):
        pstr = 'DataModel_Banter is not finished'
        return pstr

    def getPrintStringAbbrev(self):
        pstr = 'DataModel_Banter is not finished'
        return pstr




            

                        



#A DigitBelief holds a distribution of beliefs over values of a digit from 0-9.
#The distribution can have at most three elements, val1, val2, and unknown.
#Probability is distributed among these
class DigitBelief():
    def __init__(self):
        self.val1_value = '-'        #value doesn't matter if the confidence is 0
        self.val1_confidence = 0.0
        self.val2_value = '-'        #value doesn't matter if the confidence is 0
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0
        
    def setValueDefinite(self, value):
        self.val1_value = value
        self.val1_confidence = 1.0
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 0.0

    #sets the primary value val1_value to digit_value with belief=prob, the remaining belief goes to val_unknown
    def setValueProb(self, digit_value, prob):
        self.val1_value = digit_value
        self.val1_confidence = prob
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0-prob

    def setValueUnknown(self):
        self.val1_value = '-'
        self.val1_confidence = 0.0
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0

    #returns a tuple (value, confidence)
    def getHighestConfidenceValue(self):
        max_confidence = max(self.val1_confidence, self.val2_confidence, self.val_unknown_confidence)
        if max_confidence == self.val1_confidence:
            return (self.val1_value, self.val1_confidence)
        elif max_confidence == self.val2_confidence:
            return (self.val2_value, self.val2_confidence)
        else:
            return ('?', self.val_unknown_confidence)
        

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        temp_list = [(self.val1_value, self.val1_confidence),\
                     (self.val2_value, self.val2_confidence),\
                     ('?', self.val_unknown_confidence)]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        return '[ \'' + str(temp_list[0][0]) + '\':' + format(temp_list[0][1], '.2f') + ', \''\
            + str(temp_list[1][0]) + '\':' + format(temp_list[1][1], '.2f') + ', \''\
            + str(temp_list[2][0]) + '\':' + format(temp_list[2][1], '.2f') + ' ]'

    def getPrintStringAbbrev(self):
        temp_list = [(self.val1_value, self.val1_confidence),\
                     (self.val2_value, self.val2_confidence),\
                     ('?', self.val_unknown_confidence)]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        return str(temp_list[0][0])

    def getConfidenceInValue(self, target_value):
        if target_value == self.val1_value:
            return self.val1_confidence
        if target_value == self.val2_value:
            return self.val2_confidence
        return 0.0




#A BooleanBelief represents belief distributed between the value 0=false and 1=true
#In other words, this is a binomial.
class BooleanBelief():
    def __init__(self):
        self.true_confidence = .5  #belief in the value 1=true, initialize as totally unknown

    def setBeliefInTrue(self, val):
        self.true_confidence = val

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        return '[ ' + format(self.true_confidence, '.2f') + ' ]'
        


#An OrderedMultinomialBelief represents belief distributed between several ordered values.
class OrderedMultinomialBelief():
    def __init__(self, value_list):
        #sets up:
        #self.value_list
        #self.confidence_list
        #self.value_name_index_map
        if len(value_list) == 0:
            value_list = [None]
        self.resetValueList(value_list)

    def resetValueList(self, value_list):
        self.value_list = value_list[:]
        conf = 1.0 / len(value_list)
        self.confidence_list = len(value_list) * [ 1.0/len(value_list) ]
        self.value_name_index_map = {}
        for i in range(0, len(value_list)):
            self.value_name_index_map[value_list[i]] = i

    def setEquallyDistributed(self):
        conf = 1.0 / len(self.value_list)
        self.confidence_list = len(self.value_list) * [ 1.0/len(self.value_list) ]

    def setAllConfidenceInOne(self, all_confidence_value):
        self.confidence_list = len(self.value_list) * [ 0.0 ]
        index = self.value_name_index_map.get(all_confidence_value)
        if index == None:
            print 'setAllConfidenceInOne could not find index for all_confidence_value: ' + str(all_confidence_value)
            return
        self.confidence_list[index] = 1.0

    def setAllConfidenceInTwo(self, half_confidence_value_1, half_confidence_value_2):
        self.confidence_list = len(self.value_list) * [ 0.0 ]
        index1 = self.value_name_index_map.get(half_confidence_value_1)
        index2 = self.value_name_index_map.get(half_confidence_value_2)
        if index1 == None:
            print 'setAllConfidenceInTwo could not find index for all_confidence_value: ' + str(half_confidence_value_1)
            return
        if index2 == None:
            print 'setAllConfidenceInTwo could not find index for all_confidence_value: ' + str(half_confidence_value_2)
            return
        self.confidence_list[index1] = .5
        self.confidence_list[index2] = .5


    #returns -1 if the dominant value is out of range
    # (maybe None would be better?)
    def getDominantValue(self):
        max_confidence = 0.0
        max_value = -1
        for i in range(0, len(self.value_list)):
            confidence = self.confidence_list[i]
            if confidence > max_confidence:
                max_confidence = confidence
                max_value = self.value_list[i]
        return max_value

    #returns a tuple of tuples ((max_value, max_conf), (second_max_value, second_max_conf))
    def getTwoMostDominantValues(self):
        max_conf = 0.0
        max_value = -1
        second_max_conf = 0.0
        second_max_value = 0.0
        for i in range(0, len(self.value_list)):
            value = self.value_list[i]
            confidence = self.confidence_list[i]
            if confidence > max_conf:
                second_max_value = max_value
                second_max_conf = max_conf
                max_conf = confidence
                max_value = value
            elif confidence > second_max_conf:
                second_max_value = value
                second_max_conf = confidence
        ret = ((max_value, max_conf), (second_max_value, second_max_conf))
        return ret

    def getValueConfidence(self, item_value_name):
        index = self.value_name_index_map.get(item_value_name)
        if index == None:
            print 'getValueConfidence could not find index for item_value_name: ' + str(item_value_name)
            return None
        return self.confidence_list[index]
    

    #sets the confidence in item_name to new_item_confidence
    #then adjusts the confidence in all other values to normalize to 1
    def setValueConfidenceNormalizeOthers(self, item_name, new_item_confidence):
        if new_item_confidence < 0 or new_item_confidence > 1:
            print 'setValueConfidenceNormalizeOthers got new_item_confidence ' + str(new_item_confidence) + ' out of bounds for item_name: ' + str(item_name)
            new_item_confidence = min(1, max(0, new_item_confidence))

        item_index = self.value_name_index_map.get(item_name)
        if item_index == None:
            print 'setValueConfidenceNormalizeOthers could not find index for item_value_name: ' + str(item_value_name)
            return
        previous_conf = self.confidence_list[item_index]
        delta = new_item_confidence - previous_conf
        other_delta = -delta / (len(self.value_list) - 1)
        self.confidence_list[item_index] = new_item_confidence
        iter = 0
        while abs(other_delta) > .001:
            non_item_conf_sum = 0
            for i in range(0, len(self.value_list)):
                if i == item_index:
                    continue
                self.confidence_list[i] = max(0, min(1, self.confidence_list[i] + other_delta))
                non_item_conf_sum += self.confidence_list[i]
            #believe it or not I guessed right and got the signs correct on my first try
            other_delta = ((1 - self.confidence_list[item_index]) - non_item_conf_sum) / (len(self.value_list) - 1)
            #print str(iter) + ' conf_list: ' + str(self.confidence_list)
            #print ' non_item_conf_sum: ' + str(non_item_conf_sum) + ' other_delta: ' + str(other_delta)
            iter += 1
        

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        conf_threshold_to_print = .1     #only print confidences > threshold .1
        temp_list = []
        for i in range(0, len(self.value_list)):
            temp_list.append((self.value_list[i], self.confidence_list[i]))
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        ret_str = '[ '
        ret_str += str(temp_list[0][0]) + ':' + format(temp_list[0][1], '.2f')
        i = 1;
        while i < 3:
            if temp_list[i][1] > conf_threshold_to_print:
                ret_str += ' / ' + str(temp_list[i][0]) + ':' + format(temp_list[i][1], '.2f')
            i += 1
        ret_str += ' ]'
        return ret_str


gl_number_to_word_map = {'1':'one', '2':'two', '3':'three', '4':'four', '5':'five',\
                         '6':'six', '7':'seven', '8':'eight', '9':'nine', '0':'zero'}

gl_word_digit_to_int_map = {'one':1, 'two':2, 'three':3, 'four':4, 'five':5,\
                         'six':6, 'seven':7, 'eight':8, 'nine':9, 'zero':0}

def numericalDigitToWordDigit(numerical_digit):
    global gl_number_to_word_map
    return gl_number_to_word_map.get(numerical_digit)

def wordDigitToInt(word_digit):
    global gl_word_digit_to_int_map
    return gl_word_digit_to_int_map.get(word_digit)





def printAgentBeliefs(abbrev_p = True):
    global gl_agent
    if gl_agent.self_dialog_model == None:
        return
    #print 'self: iptr     ' + str(gl_agent.self_dialog_model.data_index_pointer.getDominantValue())
    if abbrev_p:
        print gl_agent.self_dialog_model.data_model.getPrintStringAbbrev()
    else:
        print gl_agent.self_dialog_model.data_model.getPrintString()
    #print 'partner: iptr: ' + str(gl_agent.partner_dialog_model.data_index_pointer.getDominantValue())
    if abbrev_p:
        print gl_agent.partner_dialog_model.data_model.getPrintStringAbbrev()
    else:
        print gl_agent.partner_dialog_model.data_model.getPrintString()
        



#The class, TurnTopic, holds an agent's belief about the topic(s) of the DialogActs of a turn.
#In the case of data communication, this is usually what aspect of a data model is 
#being referred to by one or more DialogActs of the turn. 
#
#In general, if the TurnTopic refers to a turn issued by self, then the referent_chain will contain
#the digit indices being sent.
#If the TurnTopic refers to a turn issued by partner, then the referent_chain will contain self's
#belief about what digits or field partner is referring to.
#
#The TurnTopic serves at least two important purposes:
#
#1. It is important in interpreting Confirmation dialog acts such as ConfirmDialogManagement,
#CorrectionDialogManagement, or CorrectionTopicInfo, 
#which occur when one party issues a confirmation or correction about the other party's utterance, 
#without re-stating the content of that utterance explicitly.
#
#2. The TurnTopic allows for dialog to adjust to change of topic. For example, if self has told area-code 
#and exchange and is now working on line-number, but partner asks "what is the area code?", then the topic 
#has shifted and self must recapitulate the topic line-number when restating the line number data.
#And conversely, the TurnTopic allows for data communication to be streamlined, with only the data 
#being transmitted but not its indices (i.e. under mild handshaking, omit declaring the field name) 
#as long as the topic (data indices) follow from the previous turn. 
#
#
#The TurnTopic might also serve as a goal stack, similar to Otto's goal stack.
#Or, we might have a separate goal stack object within a DialogModel. 
#(BTW, I would not treat this strictly as a stack; goals can be changed opportunistically,
# not necessarily in the order they may have been placed on a stack.)
#TBD as of 2016/06/27.


#
#A list of tuples whose purpose is to describe what item(s) in a data model
#are being discussed in dialog acts. For example, which digit(s) in a 
#telephone number are being referred to.
# (turn, data_index_descriptor_for_dialog_acts)
#
#where 
#
#a turn a tuple that exists on the gl_turn_history: 
# (turn_number, speaker = 'self' or 'partner', DialogAct list, utterance_word_tuple)
#
# data_index_descriptor_for_dialog_acts is a tuple:
# ( data_index_descriptor_for_data_item, data_index_descriptor_for_data_item, ...)
# that is, one data_index_descriptor_for_data_item per data item in the DialogAct list.
#
# a data_index_descriptor_for_data_item is a tuple
#of the form, ((field, value)...(data_value, value))
#This proceeds from a root of a tree to a field id for a leaf.
#For the telephone number data, the data_index_pointer will be of the form,
#  ((database_root, [database]),
#      (person_name, [person_name]),
#            (info_type, [info_type]),
#                 (field_name, field_name),
#                       (index_in_field, [index_in_field]),
#                           (data_value, [data_value]))
#
#For telephone numbers, the data_value is a number word like,  'six'
#leading to e.g.
#  ((database_root, gl_contact_database),
#      (person_name, Roger_Smith),
#           (info_type, mobile_telephone),
#               (field_name, area_code),
#                   (index_in_field, 0), 
#                       (data_value, six))
#
#However, a dialog_act_data_index_referent might also refer to a person,
#a field, or any other topic of interest.
#For a person, it might be,
#  ((database_root, gl_contact_database),
#      (person_name, Roger_Smith))
#
#The items in the dialog_act_data_index_referent_list will be newest first, 
#oldest last, just like the gl_turn_history.
#
#

class TurnTopic():
    def __init__(self):
        self.turn = None              #The complete turn tuple: (turn_number, speaker = 'self' or 'partner', DialogAct list)
                                      #under consideration by this TurnTopic
        #self.referent_chain = []     #This would be a more advanced, general way of handling TurnTopic
        self.field_name = None        #In case a data segment field was referred to in the turn.
        self.data_index_list = []     #A list of integers, the indices of the data items referred to, with respect to 
                                      #The indices of the current DataModel


    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = ''
        if self.field_name == None:
            field_name_str = 'None'
        else:
            field_name_str = self.field_name
        pstr += 'turn ' + str(self.turn[0]) + ' ' + self.turn[1] + ' field_name: ' + str(self.field_name) + ' data_index_list: ' + str(self.data_index_list)
        for da in self.turn[2]:
            pstr += '\n    ' + da.getPrintString()
        return pstr


    


#rel should be -1 or 1 for previous to or next after the topic_field passed
def getFieldRelativeToField(topic_field, rel):
    global gl_agent
    target_start_index = -100
    target_stop_index = -100

    topic_field_start_stop_indices = gl_agent.self_dialog_model.data_model.data_indices.get(topic_field)
    if rel == -1:
        target_stop_index = topic_field_start_stop_indices[0] - 1
    elif rel == 1:
        target_start_index = topic_field_start_stop_indices[1] + 1

    print ' getFieldRelativeToField(' + topic_field + ',' + str(rel) + ')'
    segment_names = gl_agent.self_dialog_model.data_model.data_indices.keys()
    for segment_name in segment_names:
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        if segment_indices[0] == target_start_index:
            return segment_name
        if segment_indices[len(segment_indices)-1] == target_stop_index:
            return segment_name

    return None
            

#
#
###############################################################################

###############################################################################
#
#
#


gl_turn_number = 0

#each turn is a tuple: (turn_number, speaker = 'self' or 'partner', DialogAct list, utterance_word_tuple)
#DialogAct list is a list of DialogAct instances, not their string versions
#for now we may not be including the utterance word tuple because that has to be gotten from the ruleProcessing side
#Each new turn is prepended to the front of the list so the most recent turn is gl_turn_number[0]
gl_turn_history = []


#A list of tuples for Request, Check, or possibly other DialogActs, that represent questions that are still pending.
#The concept is borrowed from Otto.  Experimenting with it here.
#
#It may be that a pending question list should not be necessary because the question is in the 
#gl_turn_history.
#On the other hand, we might give pending questions different status than normal turn history because
#they represent unfulfilled goals or discussion points in the conversation.
#
#(turn_number, speaker = 'self' or 'partner', DialogAct, utterance_word_tuple, question_response_options_tuple)
#These are ordered by turn, most recent first.
#Unlike gl_turn_history, there is only one DialogAct per tuple, so if a turn includes multiple
#questions, these will be stacked up.
#question_response_options_tuple is a tuple of LogicalForms which are acceptable responses to the question.
#If handleAnyPendingQuestion(input_da_list) has input_da_list[0] match any acceptable responses to a pending
#question, then the question handler will be called.
gl_pending_question_list = []



#Returns True if the question was added, False if it was already there
def pushQuestionToPendingQuestionList(turn_number, speaker, da, utterance_word_tuple, question_response_options_tuple):
    global gl_pending_question_list
    for question_tuple in gl_pending_question_list:
        if question_tuple[1] == speaker and question_tuple[2] == da:
            return False
    gl_pending_question_list.append((turn_number, speaker, da, utterance_word_tuple, question_response_options_tuple))
    return True


#Returns the full question_tuple if the question speaker and dialog act is on the gl_pending_question_list.
def getQuestionTupleOnPendingQuestionList(speaker, da):
    global gl_pending_question_list
    for question_tuple in gl_pending_question_list:
        if question_tuple[1] == speaker and question_tuple[2] == da:
            return question_tuple
    return None


#Returns True if the question is on the gl_pending_question_list, False if not
def removeQuestionFromPendingQuestionList(speaker, da):
    global gl_pending_question_list
    new_ql = []
    for question_tuple in gl_pending_question_list:
        if question_tuple[1] == speaker and question_tuple[2] == da:
            continue
        new_ql.append(question_tuple)
    gl_pending_question_list = new_ql


def clearPendingQuestions():
    global gl_pending_question_list
    gl_pending_question_list = []
    
    

    
#This is called when a ConfirmDialogManagement, CorrectionTopicInfo, or InformRoleInterpersonal is encountered
#from a "yes," "no," or "not sure" utterance, and possibly from other DialogActs.
#da_list is the input DialogActs
#we use only the first DialogAct on da_list, da0
#This checks the gl_pending_question_list and looks at each questions' question_response_options_tuple.
#If one of these matches da0, then...
#If there's a pending question that da_list addresses, this [somehow] assembles a ret_da_response list
#which it returns.
#(turn_number, speaker = 'self' or 'partner', DialogAct, utterance_word_tuple, question_response_options_tuple)
#If no question is handled, this returns None
#Returns ( ret_das, turn_topic) or None
def handleAnyPendingQuestion(da_list):
    global gl_pending_question_list
    da0 = da_list[0]
    print 'handleAnyPendingQuestion ' + str(len(da_list)) + ' gl_pending_question_list: ' + str(len(gl_pending_question_list))
    print '    da:' + da0.getPrintString()

    for question_tuple in gl_pending_question_list:
        question_response_options_tuple = question_tuple[4]
        for response_option in question_response_options_tuple:
            #print '  ' + response_option.getPrintString()
            if response_option.getPrintString() == da0.getPrintString():
                return handleResponseToQuestion(question_tuple, da_list)
    #print 'handleAnyPendingQuestion returning (None, None)'
    return (None, None)



#This is to allow different pending questions posed by self or partner to invoke actions when some response
#is finally received from the other party.
#question_tuple:
# (turn_number, speaker = 'self' or 'partner', DialogAct, utterance_word_tuple, question_response_options_tuple)
#Returns ( ret_das, turn_topic )  or None
def handleResponseToQuestion(question_tuple, response_da_list):
    da0 = response_da_list[0]
    print 'handleResponseToQuestion saw response ' + da0.getPrintString() + \
        ' to question (' + str(question_tuple[0]) + ', ' + question_tuple[1] + ' ' + question_tuple[2].getPrintString() + ' utterance: ' + \
        question_tuple[3]

    question_da = question_tuple[2]
    question_str_da = question_da.getPrintString()
    print ' question_da : ' + question_str_da
    if question_str_da == gl_str_da_request_dm_invitation_send_receive:
        return handleResponseToDialogInvitationQuestion(question_da, response_da_list)
    if question_str_da == gl_str_da_request_dm_invitation_receive:
        return handleResponseToDialogInvitationQuestion(question_da, response_da_list)
    print 'handleResponseToQuestion sees no match'
    return (None, None)





#A list of DialogActs that represent the most recently immediate topical data objects.
#For example, the most recently discussed digit sequence.
gl_most_recent_data_topic_da_list = []


#Looks at the initial DialogAct of user_da_list to determine the principle Intent and dialog level (this could be improved).
#Based on this, this calls out to a handler for the user input dialog acts passed.
#It gets back a list of response dialog acts, and possibly a TurnTopic instance.
#Stuffs gl_turn_history with da_response and
#puts the TurnTopic into gl_agent's self dialog model turn_topic list, if applicable.
#Returns a tuple:  (  da_response=list of DialogActs, turn_topic  )
def generateResponseToInputDialog(user_da_list):
    print 'generateResponseToInputDialog user_da_list len: ' + str(len(user_da_list))
    global gl_turn_history
    global gl_turn_number
    global gl_most_recent_data_topic_da_list
    global gl_agent

    if gl_stop_main_loop:
        return ([], None)

    if len(user_da_list) == 0:
        print 'what? user_da_list length is 0'
        ret_das = [ gl_da_misalignment_self_hearing_or_understanding ]
        return (ret_das, None)

    gl_turn_history.insert(0, (gl_turn_number, 'partner', user_da_list))
    gl_turn_number += 1
    datt_response = None    #a tuple: ( da_list, turn_topic )
    
    if user_da_list[0].intent == 'InformTopicInfo':
        datt_response = handleInformTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'InformDialogManagement':
        datt_response = handleInformDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'InformRoleInterpersonal':
        datt_response = handleInformRoleInterpersonal(user_da_list)
    elif user_da_list[0].intent == 'RequestTopicInfo':
        datt_response = handleRequestTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'RequestDialogManagement':
        datt_response = handleRequestDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'CheckTopicInfo':
        datt_response = handleCheckTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'CheckDialogManagement':
        datt_response = handleCheckDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'ConfirmTopicInfo':
        datt_response = handleConfirmTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'ConfirmDialogManagement':
        datt_response = handleConfirmDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'CorrectionTopicInfo':
        datt_response = handleCorrectionTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'CorrectionDialogManagement':
        datt_response = handleCorrectionDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'RequestAction':
        datt_response = handleRequestAction(user_da_list)

    print '......'
                           
    if datt_response == None:
        print '!Did not generate a response to user input DialogActs:'
        for user_da in user_da_list:
            user_da.printSelf()
        da_response = []
        turn_topic = None
    else:
        da_response = datt_response[0]
        turn = (gl_turn_number, 'self', da_response)
        gl_turn_history.insert(0, turn)
        turn_topic = datt_response[1]
        if turn_topic != None:
            turn_topic.turn = turn
            gl_agent.self_dialog_model.addTurnTopic(turn_topic)
        gl_turn_number += 1

    print 'datt_response: ' + str(datt_response)


    #Determine if this response merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_response:
        if type(da) is str:
            print '!!!!! a string was passed as a DialogAct.  use the gl_da form, not gl_str_da   !!!!'

        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_response[:]

    print ' Updating gl_most_recent_data_topic_da_list:'
    for da in gl_most_recent_data_topic_da_list:
        print da.getPrintString()
    print 'control: ' + gl_agent.self_dialog_model.control.getDominantValue()
    print ' ..'
        
    gl_agent.setTurn('partner')
    return (da_response, turn_topic)





                           


###############################
#
#Rules
#gg
#
#By convention, we'll use the following arugments in order to make it easier to keep track
#of which arguments are being referred to in the logical form processing rules.
#This does not go so far as encoding an arugment type in its alphanumeric value.
#Not sure if that would be desirable or not.
#
# $1 - $19     digit or other alphanumeric chars  e.g. $D_1, $D_12
# $20          ItemTypeName        (type of name, "my name", "your name"
# $40 - $49    Name, InfoNameCat   (a name, e.g. "person", "computer", "Dave")
# $25 - $29    ItemTypeChar        (the type of a char, e.g. digit, alphabetic, number)
# $30 - $35    FieldName
# $50 - $55    Command, Send/Receive  (tell-me / tell-you)
# $100 - $119  Grammar, Grammatical, Tense, etc.
# $120 - $124  ConfirmDialogManagement        affirmation-yes
# $125 - $129  CorrectionDialogManagement     negation, partner-correction
#


gl_da_inform_dm_greeting = rp.parseDialogActFromString('InformDialogManagement(greeting)')
gl_str_da_inform_dm_greeting = 'InformDialogManagement(greeting)'


gl_da_what_is_your_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeName(agent-name-user-perspective))')
gl_str_da_what_is_your_name = 'RequestTopicInfo(SendReceive(tell-me), ItemTypeName(agent-name-user-perspective))'

gl_str_da_agent_my_name_is = 'InformTopicInfo(agent-name-agent-perspective, Name($40))'



gl_da_what_is_my_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeName(user-name-user-perspective))')

gl_str_da_your_name_is = 'InformTopicInfo(user-name-agent-perspective, Name($40))'


#tell me
gl_da_tell_me = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me))')
gl_str_da_tell_me = 'RequestTopicInfo(SendReceive(tell-me))'

#for detecting RequestTopicInfo dialog acts that start with SendReceive(tell-me) but then have more arguments
gl_str_da_tell_me_initial = 'RequestTopicInfo(SendReceive(tell-me)'


#Use gl_da_tell_me_field instead
#"tell me the telephone number"
gl_da_tell_me_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), FieldName(telephone-number))')

#"tell you the telephone number"
gl_da_tell_you_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), FieldName(telephone-number))')

#"receive"
gl_da_receive = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(receive))')
gl_str_da_receive = 'RequestTopicInfo(SendReceive(receive))'

#"send"
gl_da_send = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(send))')
gl_str_da_send = 'RequestTopicInfo(SendReceive(send))'


#tell me your name/my name
gl_da_tell_me_item_type_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeName($20))')
gl_da_tell_you_item_type_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), ItemTypeName($20))')

gl_da_tell_you_field = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), FieldName($30))')
gl_da_tell_you_item_type_char = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), ItemTypeChar($25))')

gl_da_tell_you_field_grammar = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), FieldName($30), GrammaticalIndicative($100), GrammaticalBe($101))')
gl_str_da_tell_you_field_grammar = 'RequestTopicInfo(SendReceive(tell-you), FieldName($30), GrammaticalIndicative($100), GrammaticalBe($101))'

gl_da_tell_you_field_indexical = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), FieldName($30), Indexical($140))')


#tell me the number
gl_da_tell_me_item_type_char = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25))')
gl_str_da_tell_me_item_type_char = 'RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25))'

gl_da_tell_me_item_type_char_grammar = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25), GrammaticalIndicative($100), GrammaticalBe($101))')
gl_str_da_tell_me_item_type_char_grammar = 'RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25), GrammaticalIndicative($100), GrammaticalBe($101))'

#tell me the entire number
gl_da_tell_me_item_type_char_indexical = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25), Indexical($140))')
gl_da_tell_you_item_type_char_indexical = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), ItemTypeChar($25), Indexical($140))')

#tell me the entire number
gl_da_tell_me_item_type_char_indexical_grammar = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25), Indexical($140), GrammaticalIndicative($100), GrammaticalBe($101))')
gl_str_da_tell_me_item_type_char_indexical_grammar = 'RequestTopicInfo(SendReceive(tell-me), ItemTypeChar($25), Indexical($140), GrammaticalIndicative($100), GrammaticalBe($101))'

#what is the third digit of the exchange
gl_da_tell_me_item_type_char_indexical_of_field = rp.parseDialogActFromString('RequestTopicInfo(SendReceive($50), ItemTypeChar($25), Indexical($140), GrammaticalIndicative($100), Field($30))')
gl_str_da_tell_me_item_type_char_indexical_of_field = 'RequestTopicInfo(SendReceive($50), ItemTypeChar($25), Indexical($140), GrammaticalIndicative($100), Field($30))'




#"tell me the area code"
#"what is the area code"
gl_da_tell_me_field = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), FieldName($30))')
gl_str_da_tell_me_field = 'RequestTopicInfo(SendReceive(tell-me), FieldName($30))'

gl_da_tell_me_field_grammar = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), FieldName($30), GrammaticalIndicative($100), GrammaticalBe($101))')
gl_str_da_tell_me_field_grammar = 'RequestTopicInfo(SendReceive(tell-me), FieldName($30), GrammaticalIndicative($100), GrammaticalBe($101))'

#"tell me the entire area code"
gl_da_tell_me_field_indexical = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), FieldName($30), Indexical($140))')
gl_str_da_tell_me_field_indexical = 'RequestTopicInfo(SendReceive(tell-me), FieldName($30), Indexical($140))'

#"tell me the entire area code"
#"what is the entire area code?"
#"what is after the area code?"
gl_da_tell_me_field_indexical_grammar = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), FieldName($30), Indexical($140), GrammaticalIndicative($100), GrammaticalBe($101))')
gl_str_da_tell_me_field_indexical_grammar = 'RequestTopicInfo(SendReceive(tell-me), FieldName($30), Indexical($140), GrammaticalIndicative($100), GrammaticalBe($101))'

#"what is after that?"
gl_da_tell_me_indexical_indicative = rp.parseDialogActFromString('RequestTopicInfo(SendReceive($50), Indexical($140), GrammaticalIndicative($100))')
gl_str_da_tell_me_indexical_indicative = 'RequestTopicInfo(SendReceive($50), Indexical($140), GrammaticalIndicative($100))'


#a lone indexical like previous, eight, next, ...
gl_da_inform_ti_indexical = rp.parseDialogActFromString('InformTopicInfo(Indexical($140))')
gl_str_da_inform_ti_indexical = 'InformTopicInfo(Indexical($140))'


#"there is nothing after the area code"
gl_da_inform_ti_nothing_relative_to = rp.parseDialogActFromString('InformTopicInfo(nothing-relative-to, Indexical($140), FieldName($30))')
gl_str_da_inform_ti_nothing_relative_to = 'InformTopicInfo(nothing-relative-to, Indexical($140), FieldName($30))'

#"there is nothing after that"
gl_da_inform_ti_nothing_relative_to_indicative = rp.parseDialogActFromString('InformTopicInfo(nothing-relative-to, Indexical($140))')
gl_str_da_inform_ti_nothing_relative_to_indicative = 'InformTopicInfo(nothing-relative-to, Indexical($140))'


#"what does line number mean?"
gl_da_request_ti_meaning_of_field = rp.parseDialogActFromString('RequestTopicInfo(meaning-of, FieldName($30))')
gl_str_da_request_ti_meaning_of_field = 'RequestTopicInfo(meaning-of, FieldName($30))'


#"the area code is the first three digits of the telephone number"
gl_da_inform_ti_meaning_field = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName($30))')
gl_str_da_inform_ti_meaning_of_field = 'InformTopicInfo(meaning-of, FieldName($30))'


#gl_da_inform_ti_meaning_of_area_code = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName(area-code))')
#gl_str_da_inform_ti_meaning_of_area_code = 'InformTopicInfo(meaning-of, FieldName(area-code))'
#"the exchange is the second three digits of the telephone number"
#gl_da_inform_ti_meaning_of_exchange = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName(exchange))')
#gl_str_da_inform_ti_meaning_of_exchange = 'InformTopicInfo(meaning-of, FieldName(exchange))'
#"the line number is the last four digits of the telephone number"
#gl_da_inform_ti_meaning_of_line_number = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName(line-number))')
#gl_str_da_inform_ti_meaning_of_line_number = 'InformTopicInfo(meaning-of, FieldName(line-number))'
#"the country code is 
#gl_da_inform_ti_meaning_of_country_code = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName(country_code))')
#gl_str_da_inform_ti_meaning_of_country_code = 'InformTopicInfo(meaning-of, FieldName(country_code))'
#"the extension 
#gl_da_inform_ti_meaning_of_extension = rp.parseDialogActFromString('InformTopicInfo(meaning-of, FieldName(extension))')
#gl_str_da_inform_ti_meaning_of_extension = 'InformTopicInfo(meaning-of, FieldName(extension))'


#"this telephone number does not have a field, extension"
gl_da_inform_ti_no_field_in_number = rp.parseDialogActFromString('InformTopicInfo(no-field-in-number, FieldName($30))')
gl_str_da_inform_ti_no_field_in_number = 'InformTopicInfo(no-field-in-number, FieldName($30))'


                                                           




#gl_da_tell_me_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic($1))')
#gl_da_tell_you_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic($1))')

#gl_da_request_topic_info = rp.parseDialogActFromString('RequestTopicInfo(ItemTypeChar($1))')
#gl_str_da_request_topic_info = 'RequestTopicInfo(ItemType($1))'


#This is the initial parts of a DialogAct,
#RequestTopicInfo(request-confirmation, ItemValue(Digit($1))) or 
#RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2, ...)))
#Instead of listing out all of the argugment variations, we simply detect the initial part
#and parse out the arguments in the functions that handle this.
#The same applies for InformTopicInfo with one or more data item values.
#The following underscore _ indicates an incomplete LogicalForm.
gl_str_da_request_confirmation_ = 'RequestTopicInfo(request-confirmation'


#"is that right?"
gl_da_request_ti_request_confirmation = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation)')
gl_str_da_request_ti_request_confirmation = 'RequestTopicInfo(request-confirmation)'

#"repeat" as a RequestTopicInfo
gl_da_request_ti_repeat = rp.parseDialogActFromString('RequestTopicInfo(repeat)')
gl_str_da_request_ti_repeat = 'RequestTopicInfo(repeat)'


#Similar to above for 
#RequestDialogManagement(clarification-utterance-past, ItemValue(Digit($1))) 
#RequestDialogManagement(clarification-utterance-past, ItemValue(DigitSequence($1, $2, ...)))
gl_str_da_request_dm_clarification_utterance_ = 'RequestDialogManagement(clarification-utterance'



gl_da_say_item_type_char_is = rp.parseDialogActFromString('InformTopicInfo(SayIs(ItemTypeChar($25)))')
gl_str_da_say_item_type_char_is = 'InformTopicInfo(SayIs(ItemTypeChar($25)))'

#"the area code is"
gl_da_say_field_is = rp.parseDialogActFromString('InformTopicInfo(SayIs(FieldName($30)))')
gl_str_da_say_field_is = 'InformTopicInfo(SayIs(FieldName($30)))'


#"okay"
gl_da_affirmation_okay = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-okay)')
gl_str_da_affirmation_okay = 'ConfirmDialogManagement(affirmation-okay)'


#"yes"
gl_da_affirmation_yes = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-yes)')
gl_str_da_affirmation_yes = 'ConfirmDialogManagement(affirmation-yes)'


#"what's next", "go on"
gl_da_request_dm_proceed_with_next = rp.parseDialogActFromString('RequestDialogManagement(proceed-with-next)')
gl_str_da_request_dm_proceed_with_next = 'RequestDialogManagement(proceed-with-next)'


#"what is the rest of the telephone number?"
gl_da_request_dm_proceed_to_completion = rp.parseDialogActFromString('RequestDialogManagement(proceed-to-completion, FieldName($30))')
gl_str_da_request_dm_proceed_to_completion = 'RequestDialogManagement(proceed-to_completion, FieldName($30))'

#gl_da_affirmation_proceed_with_next = rp.parseDialogActFromString('ConfirmDialogManagement(proceed-with-next)')
#gl_str_da_affirmation_proceed_with_next = 'ConfirmDialogManagement(proceed-with-next)'






#"sorry"
gl_da_inform_dm_self_correction = rp.parseDialogActFromString('InformDialogManagement(self-correction)')
gl_str_da_inform_dm_self_correction = 'InformDialogManagement(self-correction)'



#"yes" or "okay"
gl_da_affirmation = rp.parseDialogActFromString('ConfirmDialogManagement($120)')


#"no"
gl_da_correction_dm_negation = rp.parseDialogActFromString('CorrectionDialogManagement(negation)')
gl_str_da_correction_dm_negation = 'CorrectionDialogManagement(negation)'

#"no"  This will be the interpretation of an isolated "no"
gl_da_correction_ti_negation = rp.parseDialogActFromString('CorrectionTopicInfo(negation)')
gl_str_da_correction_ti_negation = 'CorrectionTopicInfo(negation)'

#"sorry no"
gl_da_correction_ti_negation_polite = rp.parseDialogActFromString('CorrectionTopicInfo(negation-polite)')
gl_str_da_correction_ti_negation_polite = 'CorrectionTopicInfo(negation-polite)'

#"no it's"
gl_da_correction_topic_info = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction)')
gl_str_da_correction_topic_info = 'CorrectionTopicInfo(partner-correction)'

#"sorry no it's"
gl_da_correction_topic_info_negation_polite_partner_correction = rp.parseDialogActFromString('CorrectionTopicInfo(negation-polite-partner-correction)')
gl_str_da_correction_topic_info_negation_polite_partner_correction = 'CorrectionTopicInfo(negation-polite-partner-correction)'




#e.g. 'that is the [area code]'
#gl_da_correction_dm_item_type_present = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-present, FieldName($1))')
#gl_str_da_correction_dm_item_type_present = 'CorrectionTopicInfo(partner-correction-present, FieldName($1))'

#e.g.. 'that was the [area code]'
#gl_da_correction_dm_item_type_past = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-past, ItemType($1))')
#gl_str_da_correction_dm_item_type_past = 'CorrectionTopicInfo(partner-correction-past, ItemType($1))'

# "is the [area code]"
#Tense applies to GrammaticalBeIndicativeCat
# {definite-present, definite-past, indefinite-present, indefinite-past }
#This uses the RequestTopicInfo Intent because "is the" also starts a request
#So this construction is identical to gl_str_da_request_field_confirmation.
gl_da_inform_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, Tense($100), FieldName($30))')
gl_str_da_inform_field = 'RequestTopicInfo(request-confirmation, Tense($100), FieldName($30))'

#"that is the [area code]"
#$1 is one of { 
#               present-singular-far = "that is",
#               past-singular-far =    "that was",
#               present-singular-near = "this is",
#               past-singular-near =    "this was",
#               present-plural-far =    "those are", 
#               past-plural-far =       "those were",
#               present-plural-near =   "these are",
#               past-plural-near =      "these were",
#               present-singular-definite-far = "that is the",
#               past-singular-definite-far =    "that was the",
#               present-singular-definite-near = "this is the",
#               past-singular-definite-near =    "this was the",
#               present-plural-definite-far =    "those are the", 
#               past-plural-definite-far =       "those were the",
#               present-plural-definite-near =   "these are the",
#               past-plural-definite-near =      "these were the" }
gl_da_inform_field_indicative = rp.parseDialogActFromString('InformTopicInfo(grammatical-be-indicative, Grammar($100), FieldName($30))')
gl_str_da_inform_field_indicative = 'InformTopicInfo(grammatical-be-indicative, Grammar($100), FieldName($30))'


#"is the"
#{ definite-present, definite-past, indefinite-present, indefinite-past }
gl_da_inform_be_indicative = rp.parseDialogActFromString('InformTopicInfo(GrammaticalBeIndicative($100))')
gl_str_da_inform_be_indicative = 'InformTopicInfo(GrammaticalBeIndicative($100))'





#e.g. 'is the area code'
#gl_da_inform_item_type = rp.parseDialogActFromString('InformTopicInfo(info-type-present, ItemType($1))')
#gl_str_da_inform_item_type = 'InformTopicInfo(info-type-present, ItemType($1))'

#e.g. "is/was the area code"
#GrammaticalBeIndicativeCat arguments: {definite-present, definite-past, indefinite-present, indefinite-past}
gl_da_request_confirm_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, Tense($100), FieldName($30))')
gl_str_da_request_confirm_field = 'RequestTopicInfo(request-confirmation, Tense($100), FieldName($30))'

#is the area code ...?
#gl_da_request_confirm_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, Grammatical($1), FieldName($2))')
#gl_str_da_request_confirm_field = 'RequestTopicInfo(request-confirmation, Grammatical($1), FieldName($2))'



#"is six five zero the area code?"
gl_da_is_digits_1_the_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, ItemValue(Digit($1)), FieldName($30), Tense($100))')

gl_da_is_digits_2_the_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2)), FieldName($30), Tense($100))')

gl_da_is_digits_3_the_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2, $3)), FieldName($30), Tense($100))')

gl_da_is_digits_4_the_field = rp.parseDialogActFromString('RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2, $3, $4)), FieldName($30), Tense($100))')









#Readiness

gl_da_request_readiness = rp.parseDialogActFromString('RequestDialogManagement(other-readiness)')
gl_str_da_request_readiness = 'CheckDialogManagement(other-readiness)'

#"i'm ready"
gl_da_inform_self_ready = rp.parseDialogActFromString('InformDialogManagement(self-readiness)')
gl_str_da_inform_self_ready = 'InformDialogManagement(self-readiness)'

#"go on"
#gl_da_request_self_ready = rp.parseDialogActFromString('RequestDialogManagement(self-readiness)')
#gl_str_da_request_self_ready = 'RequestDialogManagement(self-readiness)'

#"i'm not ready"
gl_da_inform_self_not_ready = rp.parseDialogActFromString('InformDialogManagement(self-not-readiness)')
gl_str_da_inform_self_not_ready = 'InformDialogManagement(self-not-readiness)'

#"please wait"
gl_da_request_self_not_ready = rp.parseDialogActFromString('RequestDialogManagement(self-not-readiness)')
gl_str_da_request_self_not_ready = 'RequestDialogManagement(self-not-readiness)'

#"okay i'll wait for you"
gl_da_dm_confirm_partner_not_ready = rp.parseDialogActFromString('InformDialogManagement(confirm-partner-not-ready)')
gl_str_da_dm_confirm_partner_not_ready = 'InformDialogManagement(confirm-partner-not-ready)'

#"i'm waiting"
gl_da_self_waiting = rp.parseDialogActFromString('InformDialogManagement(declare-waiting-for-partner)')
gl_str_da_self_waiting = 'InformDialogManagement(declare-waiting-for-partner)'

#"are you waiting"
gl_da_request_are_you_waiting = rp.parseDialogActFromString('RequestDialogManagement(are-you-waiting)')
gl_str_da_request_are_you_waiting = 'RequestDialogManagement(are-you-waiting)'

#"what are you waiting for"
gl_da_request_what_are_you_waiting_for = rp.parseDialogActFromString('RequestDialogManagement(what-are-you-waiting-for)')
gl_str_da_request_what_are_you_waiting_for = 'RequestDialogManagement(what-are-you-waiting-for)'

#"i am waiting for you to be ready"
gl_da_inform_declare_waiting_for_partner = rp.parseDialogActFromString('InformDialogManagement(declare-waiting-for-partner)')
gl_str_da_inform_declare_waiting_for_partner = 'InformDialogManagement(declare-waiting-for-partner)'

#"standing by"
gl_da_standing_by = rp.parseDialogActFromString('InformDialogManagement(standing-by)')
gl_str_da_standing_by = 'InformDialogManagement(standing-by)'



#belief

#"i believe"
gl_str_da_agent_belief_yes = 'InformRoleInterpersonal(agent-belief-yes)'
gl_str_da_agent_belief_no = 'InformRoleInterpersonal(agent-belief-no)'
gl_str_da_agent_belief_unsure = 'InformRoleInterpersonal(agent-belief-unsure)'

#"i think"
gl_da_user_belief_yes = rp.parseDialogActFromString('InformRoleInterpersonal(user-belief-yes)')
gl_str_da_user_belief_yes = 'InformRoleInterpersonal(user-belief-yes)'

#"i don't think"
gl_da_user_belief_no = rp.parseDialogActFromString('InformRoleInterpersonal(user-belief-no)')
gl_str_da_user_belief_no = 'InformRoleInterpersonal(user-belief-no)'

#"i'm not sure"
gl_da_user_belief_unsure = rp.parseDialogActFromString('InformRoleInterpersonal(user-belief-unsure)')
gl_str_da_user_belief_unsure = 'InformRoleInterpersonal(user-belief-unsure)'


#"thank you"
gl_da_inform_irr_thank_you = rp.parseDialogActFromString('InformRoleInterpersonal(thank-you)')
gl_str_da_inform_irr_thank_you = 'InformRoleInterpersonal(thank-you)'


#"you're welcome"
gl_da_inform_irr_youre_welcome = rp.parseDialogActFromString('InformRoleInterpersonal(youre-welcome)')
gl_str_da_inform_irr_youre_welcome = 'InformRoleInterpersonal(youre-welcome)'






gl_da_all_done = rp.parseDialogActFromString('InformTopicInfo(all-done)')
gl_str_da_all_done = 'InformTopicInfo(all-done)'

gl_da_what = rp.parseDialogActFromString('RequestDialogManagement(what)')
gl_str_da_what = 'RequestDialogManagement(what)'

gl_da_dm_confirm_partner_not_ready = rp.parseDialogActFromString('InformDialogManagement(confirm-partner-not-ready)')
gl_str_da_dm_confirm_partner_not_ready = 'InformDialogManagement(confirm-partner-not-ready)'

#"I heard you say",  "you told me"
gl_da_i_heard_you_say = rp.parseDialogActFromString('InformDialogManagement(Inform(partner, self), Tense(past))')
gl_str_da_i_heard_you_say = 'InformDialogManagement(Inform(partner, self), Tense(past))'

#"you told me that already"
gl_da_inform_dm_past_indicative = rp.parseDialogActFromString('InformDialogManagement(Inform(partner, self), Tense(past), Grammatical(indicative))')
gl_str_da_inform_dm_past_indicative= 'InformDialogManagement(Inform(partner, self), Tense(past), Grammatical(indicative))'

#"i know that already"
gl_da_inform_dm_i_know_that = rp.parseDialogActFromString('InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense(present), GrammaticalIndicative($100))')
gl_str_da_inform_dm_i_know_that = 'InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense(present), GrammaticalIndicative($100))'

#"i knew that already" "I did get that" "I got that" "i know that'
gl_da_inform_dm_partner_confirm_understanding = rp.parseDialogActFromString('InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense($100), GrammaticalIndicative($101))')
gl_str_da_inform_dm_partner_confirm_understanding = 'InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense($100), GrammaticalIndicative($101))'

#gl_da_inform_dm_i_knew_that = rp.parseDialogActFromString('InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense(past), GrammaticalIndicative($100))')
#gl_str_da_inform_dm_i_knew_that = 'InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense(past), GrammaticalIndicative($100))'
#"I did get that"
#gl_da_inform_dm_partner_confirm_understanding = rp.parseDialogActFromString('InformDialogManagement(partner-confirm-partner-hearing-or-understanding)')
#gl_str_da_inform_dm_partner_confirm_understanding = 'InformDialogManagement(partner-confirm-partner-hearing-or-understanding)'






#"i wanted to make sure"
gl_da_inform_dm_desire_knowledge_self_high_confidence = rp.parseDialogActFromString('InformDialogManagement(Desire(self), Knowledge(self, high-confidence))')
gl_str_da_inform_dm_desire_knowledge_self_high_confidence = 'InformDialogManagement(Desire(self), Knowledge(self, high-confidence))'




#Covers a variety of InformDialogManagement misalignment conditions
gl_str_da_misalignment_any = 'InformDialogManagement(misalignment-self-hearing-or-understanding'

#i did not/do not  get/hear/understand 
gl_da_misalignment_self_hearing_or_understanding = rp.parseDialogActFromString('InformDialogManagement(misalignment-self-hearing-or-understanding)')
gl_str_da_misalignment_self_hearing_or_understanding = 'InformDialogManagement(misalignment-self-hearing-or-understanding)'

#i did not/do not  get/hear/understand  that 
gl_da_misalignment_self_hearing_or_understanding_pronoun_ref = rp.parseDialogActFromString('InformDialogManagement(misalignment-self-hearing-or-understanding, pronoun-ref)')
gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref = 'InformDialogManagement(misalignment-self-hearing-or-understanding, pronoun-ref)'

#i did not/do not  get/hear/understand  the/that    digit/area-code/exchange/line-number/...
gl_da_misalignment_self_hearing_or_understanding_field = rp.parseDialogActFromString('InformDialogManagement(misalignment-self-hearing-or-understanding, FieldName($30), Grammar($100), Grammar($101))')
gl_str_da_misalignment_self_hearing_or_understanding_field = 'InformDialogManagement(misalignment-self-hearing-or-understanding, FieldName($30), Grammar($100), Grammar($101))'


gl_da_misalignment_request_repeat = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat)')
gl_str_da_misalignment_request_repeat = 'RequestDialogManagement(misalignment-request-repeat)'


gl_da_misalignment_request_repeat_pronoun_ref = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat, pronoun-ref)')
gl_str_da_misalignment_request_repeat_pronoun_ref = 'RequestDialogManagement(misalignment-request-repeat, pronoun-ref)'


gl_da_misalignment_request_repeat_field = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat, FieldName($30))')
gl_str_da_misalignment_request_repeat_field = 'RequestDialogManagement(misalignment-request-repeat, FieldName($30))'

gl_da_inform_dm_repeat_intention = rp.parseDialogActFromString('InformDialogManagement(repeat-intention)')
gl_str_da_inform_dm_repeat_intention = 'InformDialogManagement(repeat-intention)'

gl_da_misalignment_start_again = rp.parseDialogActFromString('RequestDialogManagement(misalignment-start-again)')
gl_str_da_misalignment_start_again = 'RequestDialogManagement(misalignment-start-again)'

gl_da_request_dm_misalignment_confusion = rp.parseDialogActFromString('RequestDialogManagement(misalignment-confusion)')
gl_str_da_request_dm_misalignment_confusion = 'RequestDialogManagement(misalignment-confusion)'

gl_da_inform_dm_misalignment_confusion = rp.parseDialogActFromString('InformDialogManagement(misalignment-confusion)')
gl_str_da_inform_dm_misalignment_confusion = 'InformDialogManagement(misalignment-confusion)'


#"more slowly"
gl_da_request_dm_speed_slower = rp.parseDialogActFromString('RequestDialogManagement(speed-slower)')
gl_str_da_request_dm_speed_slower = 'RequestDialogManagement(speed-slower)'

#"more quickly"
gl_da_request_dm_speed_faster = rp.parseDialogActFromString('RequestDialogManagement(speed-faster)')
gl_str_da_request_dm_speed_faster = 'RequestDialogManagement(speed-faster)'


#gl_da_clarification_utterance_past = rp.parseDialogActFromString('RequestDialogManagement(clarification-utterance-past, ItemType($1))')
#gl_str_da_clarification_utterance_past = 'RequestDialogManagement(clarification-utterance-past, ItemType($1))'

#gl_da_clarification_utterance_present = rp.parseDialogActFromString('RequestDialogManagement(clarification-utterance-present, ItemType($1))')
#gl_str_da_clarification_utterance_present = 'RequestDialogManagement(clarification-utterance-present, ItemType($1))'


#"was/is that the area code", "did you just say the area code"
gl_da_request_clarification_utterance_field = rp.parseDialogActFromString('RequestDialogManagement(clarification-utterance, Grammar($100), FieldName($30))')
gl_str_da_request_clarification_utterance_field = 'RequestDialogManagement(clarification-utterance, Grammar($100), FieldName($30))'





                           

#area code
gl_da_field_name = rp.parseDialogActFromString('InformTopicInfo(FieldName($30))')
gl_str_da_field_name = 'InformTopicInfo(FieldName($30))'


#is not the area code
gl_da_not_field = rp.parseDialogActFromString('InformTopicInfo(not-field, FieldName($30))')
gl_str_da_not_field = 'InformTopicInfo(not-field, FieldName($30))'


gl_digit_list = ['zero', 'oh', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']


gl_da_request_action_echo = rp.parseDialogActFromString('RequestAction(speak)')
gl_str_da_request_action_echo = 'RequestAction(speak)'


"Hello?"
gl_da_misaligned_roles = rp.parseDialogActFromString('InformDialogManagement(misaligned-roles)')




#banter role, invitation and negotation about sending or receiving 

#"Would you like to send or receive a phone number?"
gl_da_request_dm_invitation_send_receive = rp.parseDialogActFromString('RequestDialogManagement(partner-desire, send-or-receive, telephone-number)')
gl_str_da_request_dm_invitation_send_receive = 'RequestDialogManagement(partner-desire, send-or-receive, telephone-number)'

#Would you like to tell me a phone number?"
gl_da_request_dm_invitation_send = rp.parseDialogActFromString('RequestDialogManagement(partner-desire, send, telephone-number)')
gl_str_da_request_dm_invitation_send = 'RequestDialogManagement(partner-desire, send, telephone-number)'

#"Would you like to get a phone number from me?"
gl_da_request_dm_invitation_receive = rp.parseDialogActFromString('RequestDialogManagement(partner-desire, receive, telephone-number)')
gl_str_da_request_dm_invitation_receive = 'RequestDialogManagement(partner-desire, receive, telephone-number)'

#"I am not yet capable of taking a telephone number from you."
gl_da_inform_dm_self_not_able_receive = rp.parseDialogActFromString('InformDialogManagement(self-capability, not-able, receive, telephone-number)')
gl_str_da_inform_dm_self_not_able_receive = 'InformDialogManagement(self-capability, not-able, receive, telephone-number)'

#"I able to tell you a telephone number."
gl_da_inform_dm_self_able_send = rp.parseDialogActFromString('InformDialogManagement(self-capability, able, send, telephone-number)')
gl_str_da_inform_dm_self_able_send = 'InformDialogManagement(self-capability, able, send, telephone-number)'








#CheckTopicInfo



#




gl_da_misaligned_index_pointer = rp.parseDialogActFromString('InformDialogManagement(misaligned-index-pointer)')
gl_da_misaligned_digit_values = rp.parseDialogActFromString('InformDialogManagement(misaligned-digit-values)')



#getting interesting when agents can talk about what they know
gl_da_inform_dm_knowledge_field = rp.parseDialogActFromString('InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense($100), FieldName($30))')
gl_str_da_inform_dm_knowledge_field = 'InformDialogManagement(Knowledge(possess, PersonRef(self)), Tense($100), FieldName($30))'


#stop, quit
gl_da_request_dm_stop_process = rp.parseDialogActFromString('RequestDialogManagement(StopProcess))')
gl_str_da_request_dm_stop_process = 'RequestDialogManagement(StopProcess))'


#gg

#
#
###############################





####
#
#Inform
#
#Proffer information about topic or dialog management.
#Assumption that the recipient's belief confidence is low.
#



#InformTopicInfo
#Proffer information about topic

#Because template rule interpretation does not support return of mutliple intents for
#the same words, InformTopicInfo has to do double duty with CheckTopicInfo.
#This is done by assuming that if self role is sending, then receipt of an InformTopicInfo
#DialogAct from partner is actually a CheckTopicInfo.
#CheckTopicInfo occurs when the information receiver has high confidence and is 
#reiterating data values for the purpose of confirmation.
#
#
def handleInformTopicInfo(da_list):
    if gl_agent.send_receive_role == 'send':
        return handleInformTopicInfo_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleInformTopicInfo_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        return handleInformTopicInfo_BanterRole(da_list)
    




#For agent send role, handle InformTopicInfo of the following kinds
#(DialogActs coming from information recipient partner):
#  - partner check-confirming digit values only.  This is actually a CheckTopicInfo dialog act,
#    but being declarative, it takes an Inform logical form.
#    In this case, try to align the partner's stated check digits with the self data model
#    in order to infer what digits the partner is checking, some of which they might have
#    checked before.  If alignment is successful and unambiguous, then it allows us to advance
#    the partner index pointer, and set self data index pointer accordingly.
#  - partner check-confirming digit values mixed with an indication of misunderstanding, e.g. what?
#    In this case, place the partner data_index_pointer at the first what?, but send
#    context digits mirroring the sender's
#
#  -note that "is the exchange six five zero" would take an InformTopicInfo(GrammaticalBeIndicative(..))
#   as its initial DialogAct so would get shoveled here, even though it really is a request
#   This is being handled by a DialogRule to intercept this.
#
#These are InformTopicInfo because we are not currently able to parse input as multiple
#candidate DialogActs with different intents.
def handleInformTopicInfo_SendRole(da_list):
    global gl_agent
    da_inform_ti = da_list[0]
    str_da_inform_ti = da_inform_ti.getPrintString()

    print 'handleInformTopicInfo_SendRole'
    #printAgentBeliefs()

    #handle "six five zero is what",  an unusual syntactic construction but legal in English
    last_da = da_list[len(da_list)-1]
    #gl_str_da_tell_me = 'RequestTopicInfo(SendReceive(tell-me))'
    if last_da.getPrintString() == gl_str_da_tell_me:
        return handleRequestTopicInfo_SendRole(da_list)

    (partner_expresses_confusion_p, last_topic_data_indices_matched_list, actual_segment_name, partner_digit_word_sequence) = \
                        comparePartnerReportedDataAgainstSelfData(da_list)

    #This is an easy out, to be made more sophisticated later
    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret_das = [gl_da_inform_dm_repeat_intention]
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        last_self_utterance_da_list = last_self_utterance_tup[2]
        #don't repeat repeat_intention
        last_self_utterance_da_list = stripDialogActsOfType(last_self_utterance_da_list,\
                                                            [ gl_str_da_inform_dm_repeat_intention, gl_str_da_correction_topic_info ])
        last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
        ret_das.extend(last_self_utterance_da_list)
        return (ret_das, last_self_turn_topic)

    #Check whether this InformTopicIfno contains a request for confirmation, e.g.
    #six three seven, right?
    #In such case, handle this as a RequestTopicInfo
    for da in da_list:
        if da.getPrintString() == gl_str_da_request_ti_request_confirmation:
            return handleRequestTopicInfo_SendRole(da_list)

    #Check whether this InformTopicInfo contains an isolated "then" or "next" preceeding a request.
    #If so, strip it off and process the request
    mapping = rp.recursivelyMapDialogRule(gl_da_inform_ti_indexical, da_inform_ti)
    if mapping != None:
        indexical = mapping.get('140')
        if indexical == 'next':
            if len(da_list) > 1:
                if da_list[1].intent == 'RequestTopicInfo':
                    return handleRequestTopicInfo_SendRole(da_list[1:])
                if da_list[1].intent == 'RequestDialogManagement':
                    return handleRequestDialogManagement(da_list[1:])


    #Check to see if partner has named the segment themselves, and if it does not match the data they repeated
    #back, as in "area code six three seven"
    for da in da_list:
        mapping = rp.recursivelyMapDialogRule(gl_da_field_name, da)
        if mapping != None:
            stated_field_name = mapping.get('30')
            print 'stated_field_name: ' + stated_field_name
            #Partner has not repeated back the digits of a recognized segment, tell them the digits of the segment they named.
            if actual_segment_name == None:
                #"the area code is six five zero"
                print 'calling handleSendSegmentChunkNameAndData(' + stated_field_name + ')'
                return handleSendSegmentChunkNameAndData(stated_field_name)
            #Partner has repeated back the digits of a recognized segment, if these digits don't match the segment name they said,
            #then tell them the correct segment name for these digits.
            if stated_field_name != actual_segment_name:
                field_data_value_list = getDataValueListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
                field_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(field_data_value_list)
                str_da_inform_be_indicative = gl_str_da_inform_be_indicative.replace('$100', 'definite-present')
                da_inform_be_indicative = rp.parseDialogActFromString(str_da_inform_be_indicative)
                str_da_field_name = gl_str_da_field_name.replace('$30', actual_segment_name)
                da_field_name = rp.parseDialogActFromString(str_da_field_name)
                ret_das = [ gl_da_correction_dm_negation, field_digit_sequence_lf, da_inform_be_indicative, da_field_name]
                turn_topic = TurnTopic()
                turn_topic.field_name = actual_segment_name
                turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
                return (ret_das, turn_topic) 
        
    
    #Only if check-confirm match was validated against self's belief model, update self's model
    #for what partner believes about the data.
    #Then send some more data.
    if len(last_topic_data_indices_matched_list) > 0:
        possiblyAdjustChunkSize(len(last_topic_data_indices_matched_list))
        #1.0 is full confidence that the partner's data belief is as self heard it
        partner_dm = gl_agent.partner_dialog_model
        newly_matched_digits = []
        for digit_i in last_topic_data_indices_matched_list:
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, 1.0)

        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()
        if len(self_belief_partner_is_wrong_digit_indices) == 0 and len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return ([gl_da_all_done], None)    #XX need to fill in the turn_topic
        else:
            #here complete the digits for the current topic before popping up to inform incorrect or unknown indices
            last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
            print 'last_self_turn_topic: ' + last_self_turn_topic.getPrintString()
            (ret_das, turn_topic) = prepareNextDataChunkToContinueSegment(digit_i)
            if ret_das != None:
                updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
                return (ret_das, turn_topic)

            #Determine whether the next field chunk follows directly from the previous field.
            #If not, we'll need to state the field name.
            print 'HITI_SR reverting to prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()'
            ( data_ret_das, turn_topic ) = prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers(True)
            updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(data_ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
            current_field_subsequent_to_previous_p = False
            print 'turn_topic.field_name: ' + str(turn_topic.field_name) + '  last_self_turn_topic.field_name: ' + str(last_self_turn_topic.field_name)
            if turn_topic.field_name != None and last_self_turn_topic.field_name != None:
                next_field = getFieldSubsequentToField(last_self_turn_topic.field_name)
                if next_field == turn_topic.field_name:
                    current_field_subsequent_to_previous_p = True
            ret_das = []
            if turn_topic.field_name != None and current_field_subsequent_to_previous_p == False:
                str_da_say_field_is = gl_str_da_say_field_is.replace('$30', turn_topic.field_name)
                da_say_field_is = rp.parseDialogActFromString(str_da_say_field_is)
                ret_das.append(da_say_field_is)
            ret_das.extend(data_ret_das)
            return (ret_das, turn_topic)

    #If partner has informed a set of digits that does not match what self has just said, but matches some
    #other segment in the data, then tell the user that.
    #Also set the data index pointer to this segment because that is what is now being discussed.
    if actual_segment_name != None:
        #segment_indices = gl_agent.self_dialog_model.data_model.data_indices.get(actual_segment_name)
        #segment_start_index = segment_indices[0]
        field_data_value_list = getDataValueListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
        field_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(field_data_value_list)
        str_da_inform_be_indicative = gl_str_da_inform_be_indicative.replace('$100', 'definite-present')
        da_inform_be_indicative = rp.parseDialogActFromString(str_da_inform_be_indicative)
        str_da_field_name = gl_str_da_field_name.replace('$30', actual_segment_name)
        da_field_name = rp.parseDialogActFromString(str_da_field_name)
        ret_das = [ field_digit_sequence_lf, da_inform_be_indicative, da_field_name]
        turn_topic = TurnTopic()
        turn_topic.field_name = actual_segment_name
        turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
        return (ret_das, turn_topic) 


    print 'handleInformTopicInfo_SendRole() dropping through HITI_SR'
    #"I'll repeat that."  gets annoying
    ret_das = [gl_da_inform_dm_repeat_intention]
    
    #This may not actually repeat what was said, e.g. if the user had shifted topic to the line number and then
    #mis-stated the digits of it.
    #(data_chunk_das, turn_topic) = prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

    last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
    print 'last_self_turn_topic: ' + last_self_turn_topic.getPrintString()
    last_self_turn_topic_first_data_index = last_self_turn_topic.data_index_list[0]
    print 'last_self_turn_topic_first_data_index: ' + str(last_self_turn_topic_first_data_index)
    (segment_name, start_index_pointer, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(last_self_turn_topic_first_data_index)
    print 'last_turn_topic_segment: ' + str(segment_name)
    (repeat_ret_das, turn_topic) = handleSendSegmentChunkNameAndData(segment_name)
    updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(repeat_ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
    ret_das.extend(repeat_ret_das)
    return (ret_das, turn_topic) 










#The partner is providing a turn containing a list of DialogActs that include information about digit data.
#(The DialogActs are strung together from a single turn utterance.)
#The DialogActs might also include indicators of confusion, such as what?
#These DialogActs need to be compared with correct digit data, partly though alignment search.
#This returns a tuple: 
# (partner_expresses_confusion_p, last_topic_data_indices_matched_list, check_match_segment_name, partner_digit_word_sequence)
#
# -partner_expresses_confusion_p will be True if the word what? is used or something similar
# -last_topic_indices_matched_list is a list of data index values from the last sent topic data digits that were matched by the partner utterance
#  The first such data index value should be the one for the first data digit sent in the last topic info turn
# -check_match_segment_name will be the name of any field that matches the reported digits, whether the previous turn 
#   topic data or not
# -partner_digit_word_sequence is the digits extracted from da_list
#
def comparePartnerReportedDataAgainstSelfData(da_list):
    global gl_agent
    print 'comparePartnerReportedDataAgainstSelfData(da_list)'
    for da in da_list:
        print '    ' + da.getPrintString()

    partner_digit_word_sequence = []
    partner_expresses_confusion_p = False

    partner_digit_word_sequence = collectDataValuesFromDialogActs(da_list, True)
    if '?' in partner_digit_word_sequence:
        partner_expresses_confusion_p = True

    #If the last self utterance turn does match the last turn_topic which contains inform topic info, then check
    #whether the partner's utterance echoes that data
    last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
    last_self_turn_topic_turn_number = last_self_turn_topic.turn[0]
    last_self_turn_topic_data_index_list = last_self_turn_topic.data_index_list
    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    last_sent_digit_value_list = []
    last_topic_data_indices_matched_list = []
    print 'last_self_turn_topic_turn_number: ' + str(last_self_turn_topic_turn_number) + ' last_self_utterance_tup[0]: ' + str(last_self_utterance_tup[0])
    if last_self_turn_topic_turn_number == last_self_utterance_tup[0]:
        last_self_utterance_da_list = last_self_utterance_tup[2]
        last_sent_digit_value_list = collectDataValuesFromDialogActs(last_self_utterance_da_list)
        last_self_turn_topic_first_data_index = last_self_turn_topic.data_index_list[0]
        print ' last_sent_digit_value_list: ' + str(last_sent_digit_value_list) + '  partner_digit_word_sequence: ' + str(partner_digit_word_sequence)
        #If fewer digits were said by the partner than the last topic info, then partner should have started from the first one
        if len(partner_digit_word_sequence) < len(last_sent_digit_value_list):
            print 'JJ'
            for i in range(0, len(partner_digit_word_sequence)):
                if last_sent_digit_value_list[i] == partner_digit_word_sequence[i]:
                    last_topic_data_indices_matched_list.append(last_self_turn_topic_first_data_index + i)
                else: 
                    break;

        #If more digits were said by the partner than the last topic info, then see if they were reciting 
        #not only the topic digits but some of the previous ones as well
        elif len(last_sent_digit_value_list) < len(partner_digit_word_sequence):
            print 'KK'
            for i in range(0, len(partner_digit_word_sequence)):
                ii = len(partner_digit_word_sequence) - 1 - i  #work backwards
                digit_i = last_self_turn_topic_data_index_list[len(last_self_turn_topic_data_index_list)-1] - i
                print 'i: ' + str(i) + ' ii: ' + str(ii) + ' digit_i: ' + str(digit_i)
                if digit_i < 0:
                    last_topic_data_indices_matched_list = []
                    break;
                self_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
                self_data_value_tuple = self_digit_belief.getHighestConfidenceValue()     
                digit_value = self_data_value_tuple[0]
                if digit_value == partner_digit_word_sequence[ii]:
                    print 'ii: ' + str(ii) + ' ' + partner_digit_word_sequence[ii]
                    last_topic_data_indices_matched_list.insert(0, digit_i)
                else: 
                    last_topic_data_indices_matched_list = []
                    break;
        #If equal number of digits were said by the partner as the last topic info, then they all must match
        elif len(last_sent_digit_value_list) == len(partner_digit_word_sequence):
            print 'LL'
            for i in range(0, len(last_sent_digit_value_list)):
                if last_sent_digit_value_list[i] == partner_digit_word_sequence[i]:
                    last_topic_data_indices_matched_list.append(last_self_turn_topic_first_data_index + i)
                else: 
                    last_topic_data_indices_matched_list = []
                    break;


    #Next try to align partner's check digit word sequence with correct data that may not have been uttered yet.
    actual_segment_names = findSegmentNameForDigitList(partner_digit_word_sequence)
    actual_segment_name = None
    if len(actual_segment_names) > 0:
        actual_segment_name = actual_segment_names[0]
    
    print 'CComparePartner returning: ' + str((partner_expresses_confusion_p, last_topic_data_indices_matched_list, actual_segment_name, partner_digit_word_sequence))
    return (partner_expresses_confusion_p, last_topic_data_indices_matched_list, actual_segment_name, partner_digit_word_sequence)




        


def handleInformTopicInfo_ReceiveRole(da_list):
    print 'handleInformTopicInfo_ReceiveRole not written yet'
    return None


def handleInformTopicInfo_BanterRole(da_list):
    
    print 'handleInformTopicInfo_BanterRole not written yet'
    return None




#InformDialogManagement
#Proffer information about dialog management
#
def handleInformDialogManagement(da_list):
    global gl_turn_number
    da_inform_dm = da_list[0]
    print 'handleInformDialogManagement'

    #handle readiness issues
    (ret_das, turn_topic) = handleReadinessIssues(da_list)
    if ret_das != None:
        print 'handleReadinessIssues returned ' + str(ret_das)
        for da in ret_das:
            print da.getPrintString()
        return (ret_das, turn_topic)

    #handle confusion issues
    (ret_das, turn_topic) = handleConfusionIssues(da_list)
    if ret_das != None:
        print 'handleConfusionIssues returned ' + str(ret_das)
        for da in ret_das:
            print da.getPrintString()
        gl_agent.setControl('self')      #user asks a question so takes control
        return (ret_das, turn_topic) 

    if gl_agent.send_receive_role == 'send':
        return handleInformDialogManagement_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleInformDialogManagement_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        da0 = da_list[0]
        str_da0 = da0.getPrintString()
        print 'str_da0: ' + str_da0
        if str_da0 == gl_str_da_inform_dm_greeting:
            #allow "yes" and "no"
            possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,\
                                                       gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure)

            removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
            pushQuestionToPendingQuestionList(gl_turn_number, 'self', gl_da_request_dm_invitation_send_receive, 
                                              str_da0, (possible_answers_to_invitation_question))
            return ([gl_da_inform_dm_greeting, gl_da_request_dm_invitation_send_receive], None)   #XX need to fill in the turn_topic
        return ([ gl_da_misalignment_self_hearing_or_understanding ],  None)  #XX need to fill in the turn_topic
                           
    
#returns a text string
def getTextForDialogActList(da_list):
    output_word_list = getWordsForDialogActList(da_list)
    return ' '.join(output_word_list)

#returns a list of words
def getWordsForDialogActList(da_list):
    output_word_list = []
    for da in da_list:
        da_generated_word_list = rp.generateTextFromDialogAct(da)
        if da_generated_word_list == None:
            print 'could not generate a string from da'
        else:
            output_word_list.extend(da_generated_word_list)
    return output_word_list




def handleInformDialogManagement_SendRole(da_list):
    print 'handleInformDialogManagement_SendRole'
    global gl_agent
    da_inform_dm = da_list[0]
    str_da_inform_dm = da_inform_dm.getPrintString()
    for da in da_list:
        print '    ' + da.getPrintString()

    #handle "i already know the area code"
    mapping = rp.recursivelyMapDialogRule(gl_da_inform_dm_knowledge_field, da_inform_dm)
    #print 'mapping: ' + str(mapping)
    if mapping != None:
        field_name = mapping.get('30')
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])

        
        #da_list = last_self_utterance_tup[2]
        #for da in da_list:
        #    if da.getPrintString().find(gl_str_da_misalignment_any) >= 0:
        #        print 'handleInformDialogManagement_SendRole sees that the last self utterance had a misalignment ' 
        #        print '   ' + da.getPrintString()
        #        print ' returning []'
        #        return ([], None)   #XX need to fill in the turn_topic

        updateBeliefInPartnerDataStateForDataField(field_name, gl_confidence_for_confirm_affirmation_of_data_value)

        #printAgentBeliefs()
        (data_chunk_das, turn_topic) = prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers(True)
        updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(data_chunk_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
        ret_das = [ gl_da_affirmation_okay]
        ret_das.extend(data_chunk_das)

        return (ret_das, turn_topic) 

    #handle "I did not get that"
    if str_da_inform_dm == gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref: 
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        if last_self_utterance_tup != None:
            last_self_utterance_das = last_self_utterance_tup[2]
            last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
            return (last_self_utterance_das_stripped, None)   #XX need to fill in the turn_topic

    #print 'str_da_inform_dm: ' + str_da_inform_dm
    #print 'gl_da_misalignment_self_hearing_or_understanding_item_type: ' + gl_da_misalignment_self_hearing_or_understanding_item_type.getPrintString()
    #handle "I did not understand the area code, etc"
    mapping = None
    mapping = rp.recursivelyMapDialogRule(gl_da_misalignment_self_hearing_or_understanding_field, da_inform_dm)
    if mapping != None:
        misunderstood_field_name = mapping.get('30')
        if misunderstood_field_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
            #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
            chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(misunderstood_field_name)
            for i in range(chunk_indices[0], chunk_indices[1] + 1):
                data_index_pointer = gl_10_digit_index_list[i]
                gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
            return handleSendSegmentChunkNameAndData(misunderstood_field_name)

    #handle "that was six five zero, right?"
    for da in da_list:
        if da.getPrintString() == gl_str_da_request_ti_request_confirmation:
            return handleRequestTopicInfo_SendRole(da_list)

    #handle "you told me that already", "i know that already" "I did get that" "I knew that already"
    mapping = rp.recursivelyMapDialogRule(gl_da_inform_dm_partner_confirm_understanding, da_inform_dm)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_inform_dm_past_indicative, da_inform_dm)
    if mapping != None:
        last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
        #print 'I know that already'
        #printAgentBeliefs(False)
        at_least_one_digit_low_confidence_p = False
        for digit_i in last_self_turn_topic.data_index_list:
            self_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            self_data_value_tuple = self_digit_belief.getHighestConfidenceValue()     
            correct_digit_i_value = self_data_value_tuple[0]
            partner_digit_i_belief = gl_agent.partner_dialog_model.data_model.data_beliefs[digit_i]
            partner_correct_value_confidence = partner_digit_i_belief.getConfidenceInValue(correct_digit_i_value)
            #print 'correct_digit_i_value: ' + str(correct_digit_i_value) + ' partner_digit_i_belief: ' + partner_digit_i_belief.getPrintString() + ' partner_correct_value_confidence: ' + str(partner_correct_value_confidence)
            if partner_correct_value_confidence > 0 and partner_correct_value_confidence < gl_confidence_in_partner_belief_to_double_check:
                at_least_one_digit_low_confidence_p = True
                break
        #If we had low confidence, return "i wanted to make sure you got it"
        synth_confirm_da_list = [ gl_da_affirmation_yes ]
        (ret_das, turn_topic) = handleConfirmDialogManagement_SendRole(synth_confirm_da_list, True)
        print 'handleInformDialogManagement_SendRole()  returning ret_das: '
        for da in ret_das:
            print '   ' + da.getPrintString()
        if at_least_one_digit_low_confidence_p:
            ret_das.insert(0, gl_da_inform_dm_desire_knowledge_self_high_confidence)
        return (ret_das, turn_topic)


    print 'handleInformDialogManagement_SendRole dropping through returning None'
    return None


def handleInformDialogManagement_ReceiveRole(da_list):
    print 'handleInformDialogManagement_ReceiveRole not written yet'
    return None


def handleInformDialogManagement_BanterRole(da_list):
    print 'handleInformDialogManagement_BanterRole not written yet'
    return None






def handleInformRoleInterpersonal(da_list):
    print 'handleInformRoleInterpersonal'
    da0 = da_list[0]
    str_da0 = da0.getPrintString()

    if str_da0 == gl_str_da_user_belief_yes or str_da0 == gl_str_da_user_belief_no or str_da0 == gl_str_da_user_belief_unsure:
        (ret_das, turn_tuple) = handleAnyPendingQuestion(da_list)
        if ret_das != None:
            return (ret_das, turn_tuple)

    if str_da0 == gl_str_da_inform_irr_thank_you:
        if gl_agent.send_receive_role == 'banter':
            return ([ gl_da_inform_irr_youre_welcome ], None)   #XX need to fill in the turn_topic

        #If partner says "thank you" while self is in Send mode and self has just transmitted
        #information, then accept the thank you as a Confirmation
        if gl_agent.send_receive_role == 'send':

            #strip out the thank yous from the da list passed
            da_list_no_thankyou = []
            for da in da_list:
                str_da = da.getPrintString();
                if str_da.find(gl_str_da_inform_irr_thank_you) < 0:
                    da_list_no_thankyou.append(da)
                    
            if len(da_list_no_thankyou) < 1:
                da_list_no_thankyou.append(gl_da_affirmation_yes)

            #force_declare_segment_name = True, but is this really necessary?
            ret = handleConfirmDialogManagement_SendRole(da_list_no_thankyou, True) 
            if ret == None:
                return None
            confirm_da_list = ret[0]
            turn_topic = ret[1]
            confirm_da_list.insert(0, gl_da_inform_irr_youre_welcome)
            return (confirm_da_list, turn_topic) 

    #if the first da is "i think", then strip this off and try to handle the rest of the dialog acts
    if str_da0 == gl_str_da_user_belief_yes:
        ( ret_das, turn_topic ) = generateResponseToInputDialog(da_list[1:])
        if ret_das != None:
            return (ret_das, turn_topic)

    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    return (ret_das, None)   #XX need to fill in the turn_topic






####
#
#Request
#
#Request information about topic or dialog management,
#or request adjustment in dialog management protocol.
#Assumption that the speaker's belief confidence is low.
#

def handleRequestTopicInfo(da_list):
    global gl_most_recent_data_topic_da_list
    da_request_topic_info = da_list[0]

    #Determine if the utterance from partner merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_list:
        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_list[:]


    #handle 'User: what is your name'
    #rp.setTellMap(True)
    mapping = rp.recursivelyMapDialogRule(gl_da_what_is_your_name, da_request_topic_info)
    #print 'mapping: ' + str(mapping)
    if mapping != None:
        str_da_my_name_is = gl_str_da_agent_my_name_is.replace('$40', gl_agent.name)
        da_my_name_is = rp.parseDialogActFromString(str_da_my_name_is)
        gl_agent.setControl('partner')   #user is driving 
        return ([da_my_name_is], None)   #XX need to fill in the turn_topic

    #handle 'User: what is my name'
    mapping = rp.recursivelyMapDialogRule(gl_da_what_is_my_name, da_request_topic_info)
    if mapping != None:
        str_da_agent_belief_yes = gl_str_da_agent_belief_yes
        da_agent_belief_yes = rp.parseDialogActFromString(str_da_agent_belief_yes)
        str_da_your_name_is = gl_str_da_your_name_is.replace('$40', gl_agent.partner_name)
        da_your_name_is = rp.parseDialogActFromString(str_da_your_name_is)
        gl_agent.setControl('partner')   #user is driving 
        return ([da_agent_belief_yes, da_your_name_is], None)  #XX need to fill in the turn_topic

    #handle "what does line number mean?"
    mapping = rp.recursivelyMapDialogRule(gl_da_request_ti_meaning_of_field, da_request_topic_info)
    if mapping != None:
        field_name = mapping.get('30')
        if field_name in gl_telephone_number_field_names:
            str_da_inform_ti_meaning_of_field = gl_str_da_inform_ti_meaning_of_field.replace('$30', field_name)
            da_inform_ti_meaning_of_field = rp.parseDialogActFromString(str_da_inform_ti_meaning_of_field)
            ret_das = [ da_inform_ti_meaning_of_field ]
            return (ret_das, None)

    if gl_agent.send_receive_role == 'send':
        return handleRequestTopicInfo_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleRequestTopicInfo_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        return handleRequestTopicInfo_BanterRole(da_list)



#RequestTopicInfo
#Request information about topic
#
def handleRequestTopicInfo_SendRole(da_list):
    global gl_agent
    da_request_ti = da_list[0]
    str_da_request_ti = da_request_ti.getPrintString()

    print 'handleRequestTopicInfo da_list: '
    for da in da_list:
        print '     ' + da.getPrintString()

    clearPendingQuestions()

    #handle tell me what is, which produces a RequestTopicInfo(SendReceive(tell-me)) that might be followed by a
    #more specific RequestTopicInfo(SendReceive(tell-me) (one with arguments)
    #In this case, strip off the first isolated RequestTopicInfo(SendReceive(tell-me))
    if len(da_list) > 1:
        if da_request_ti.getPrintString() == gl_str_da_tell_me:
            da1 = da_list[1]
            if da1.getPrintString().find(gl_str_da_tell_me_initial) == 0:
                print 'stripped redundant RequestTopicInfo(SendRecieve(tell-me))'
                da_list = da_list[1:]
                da_request_ti = da_list[0]


    #handle "please repeat..."
    #replace the repeat request with a "tell-me"
    if str_da_request_ti == gl_str_da_request_ti_repeat:
        synth_da_list = [ gl_da_tell_me ]
        synth_da_list.extend(da_list[1:])
        return handleRequestTopicInfo_SendRole(synth_da_list)

    #This is probably superfluous, covered by the tell me the X? below.
    #handle 'User: send me the phone number'
    #rp.setTellMap(True)
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_phone_number, da_request_ti)
    #print 'mapping: ' + str(mapping)
    if mapping != None:
        gl_agent.setRole('send', gl_default_phone_number)
        #it would be best to spawn another thread to wait a beat then start the
        #data transmission process, but return okay immediately.
        #do that later
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ da_segment_name ]
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
        ret_das.extend(data_chunk_das)
        gl_agent.setControl('self')      #start the main task, putting the computer agent in control
        return (ret_das, turn_topic)

    #handle "User: what is the area code"
    #handle "User: tell me the area code"
    field_name = None
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field, da_request_ti)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_grammar, da_request_ti)
    if mapping != None:
        field_name = mapping.get('30')
    #handle "User: tell me the number"  
    #"number" can mean digit or telephone number. Here, the utterance does not include an indexical
    #like "third number", so we interpret it as the telephone number
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char, da_request_ti)
        if mapping == None:
            mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_grammar, da_request_ti)
        if mapping != None:
            num_name = mapping.get('25')
            if num_name == 'digit':
                field_name = 'telephone-number'
    print 'TTTT field_name: ' + str(field_name) + ' mapping: ' + str(mapping)
    if field_name == 'telephone-number':
        gl_agent.setRole('send', gl_default_phone_number)
        initializeStatesToSendPhoneNumberData(gl_agent)
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ da_segment_name ]
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
        ret_das.extend(data_chunk_das)
        gl_agent.setControl('self')      #start the main task, putting the computer agent in control
        return (ret_das, turn_topic)

    #handle 'User: what is the area code', etc.
    if field_name != None:
        if gl_agent.send_receive_role == 'send':
            #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
            chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(field_name)
            if chunk_indices == None:
                str_da_inform_ti_no_field_in_number = gl_str_da_inform_ti_no_field_in_number.replace('$30', field_name)
                da_inform_ti_no_field_in_number = rp.parseDialogActFromString(str_da_inform_ti_no_field_in_number)
                ret_das = [ da_inform_ti_no_field_in_number ]
                return (ret_das, None)
            for i in range(chunk_indices[0], chunk_indices[1] + 1):
                data_index_pointer = gl_10_digit_index_list[i]
                gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
            gl_agent.setControl('partner')      #a subtask driven by partner, they are taking control
            return handleSendSegmentChunkNameAndData(field_name)


    #handle "User: what is the entire area code" 
    #handle "User: tell me the entire area code"
    num_name = None
    field_name = None
    grammatical_be = None
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_indexical, da_request_ti)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_indexical_grammar, da_request_ti)
    if mapping != None:
        print ' found mapping WW'
        field_name = mapping.get('30')
        indexical = mapping.get('140')
    #handle "User: tell me the entire number", "tell me the third digit"
    #"number" can mean digit or telephone number. Here, the utterance does not include an indexical
    #like "third number", so we interpret it as the telephone number
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_indexical, da_request_ti)
        if mapping == None:
            mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_indexical_grammar, da_request_ti)
            #print 'HHH mapping: ' + str(mapping)
        if mapping != None:
            print ' found mapping YY'
            num_name = mapping.get('25')   #ItemTypeChar($25)
            if num_name == 'digit':
                field_name = 'telephone-number'
                indexical = mapping.get('140')
                grammatical_be = mapping.get('101')
            #really, "field" should not be considered an ItemTypeCharCat.
            elif num_name == 'field':
                field_name = 'segment'
                indexical = mapping.get('140')
                grammatical_be = mapping.get('101')

    if mapping == None:
        print ' trying mapping   gl_da_tell_me_item_type_char_indexical_of_field '
        #what is the third digit of the exchange?
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_indexical_of_field, da_request_ti)
        if mapping != None:
            num_name = mapping.get('25')
            if num_name == 'digit':
                field_name = mapping.get('30')
                indexical = mapping.get('140')

    #handle 'User: what is the entire telephone number?', etc.
    if field_name == 'telephone-number' and indexical == 'entire':
        gl_agent.setRole('send', gl_default_phone_number)
        initializeStatesToSendPhoneNumberData(gl_agent)
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ da_segment_name ]
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'telephone-number', True)
        ret_das.extend(data_chunk_das)
        gl_agent.setControl('self')      #start the main task, putting the computer agent in control
        return (ret_das, turn_topic)

    #handle 'User: what is the entire area code', etc.
    if field_name != None and field_name != 'segment' and indexical == 'entire':
        #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
        chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(field_name)
        for i in range(chunk_indices[0], chunk_indices[1] + 1):
            data_index_pointer = gl_10_digit_index_list[i]
            gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
        gl_agent.setControl('partner')      #a subtask driven by partner, they are taking control
        return handleSendSegmentChunkNameAndData(field_name)

    #handle 'what is the third digit?', 'what is the third digit of the exchange?'
    global gl_indexical_relative_map
    if field_name != None and field_name != 'segment' and \
             (indexical in gl_indexical_relative_map.keys()) and grammatical_be != 'present-plural':
        target_digit_ith = gl_indexical_relative_map.get(indexical)
        target_digit_i = getDigitIndexForFieldRelativeIndex(field_name, target_digit_ith)
        print 'GGG field_name: ' + field_name + ' target_digit_ith: ' + str(target_digit_ith) + ' ' + str(target_digit_i)
        if target_digit_i < 0:
            print 'handleRequestTopicInfo_SendRole indexical could not find a target_digit_i for field ' + field_name + ' ith ' + str(target_digit_ith)
            return (None, None)
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[target_digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()
        digit_value = data_value_tuple[0]
        digit_lf = synthesizeLogicalFormForDigitOrDigitSequence([digit_value])
        turn_topic = TurnTopic()
        turn_topic.data_index_list = [target_digit_i]
        return ( [digit_lf], turn_topic)

    #handle "what is the last digit?", "what is the last digit of the exchange?"
    if field_name != None and field_name != 'segment' and \
                  (indexical == 'final' or indexical == 'last') and (grammatical_be != 'present-plural'):
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[field_name]
        segment_end_index = segment_indices[1]
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[segment_end_index]
        data_value_tuple = digit_belief.getHighestConfidenceValue()
        digit_value = data_value_tuple[0]
        digit_lf = synthesizeLogicalFormForDigitOrDigitSequence([digit_value])
        turn_topic = TurnTopic()
        turn_topic.data_index_list = [segment_end_index]
        return ( [digit_lf], turn_topic)

    #handle "what is after the area code?"
    if field_name != None and field_name != 'segment' and (indexical == 'previous' or indexical == 'next'):
        print 'A1 '
        rel = 0
        if indexical == 'previous':
            rel = -1
        elif indexical == 'next':
            rel = 1
        if rel != 0:
            adjacent_field = getFieldRelativeToField(field_name, rel)
            print 'adjacent_field: ' + str(rel) + ' ' + str(adjacent_field)
            if adjacent_field != None:
                return handleSendSegmentChunkNameAndData(adjacent_field)
            #nothing rel to field_name
            str_da_nothing_rel_to = gl_str_da_inform_ti_nothing_relative_to.replace('$140', indexical)
            str_da_nothing_rel_to = str_da_nothing_rel_to.replace('$30', field_name)
            da_nothing_rel_to = rp.parseDialogActFromString(str_da_nothing_rel_to)
            return ([ da_nothing_rel_to ], None)

    #handle "what is the next segment?"
    if field_name == 'segment':
        #'what is the first part?"
        print 'grammatical_be: ' + str(grammatical_be)
        if grammatical_be == 'present-singular' or grammatical_be == 'past-singular':
            if indexical == 'first' or indexical == 'middle' or indexical == 'last':
                (segment_name, start_index_pointer, chunk_size) = findSegmentNameAndChunkSizeForIndexical(indexical)
                (ret_das, turn_topic) = handleSendSegmentChunkNameAndData(segment_name)
                return (ret_das, turn_topic)
        rel = 0
        #'what is the next part?"
        if indexical == 'previous':
            rel = -1
        elif indexical == 'next':
            rel = 1
        if rel != 0:
            last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
            last_topic_field = last_self_turn_topic.field_name
            print 'last_topic_field A: ' + str(last_topic_field)
            if last_topic_field == None:
                last_digit_list = getDataValuesForDataIndices(last_self_turn_topic.data_index_list)
                last_topic_field_list = findSegmentNameForDigitList(last_digit_list)
                if len(last_topic_field_list) > 0:
                    last_topic_field = last_topic_field_list[0]
                print 'last_topic_field B: ' + str(last_topic_field)
                #try to return previous or next with respect to topic field
            if last_topic_field != None:
                adjacent_field = getFieldRelativeToField(last_topic_field, rel)
                print 'adjacent_field: ' + str(rel) + ' ' + str(adjacent_field)
                if adjacent_field != None:
                    return handleSendSegmentChunkNameAndData(adjacent_field)
                #nothing rel to last_topic_field
                str_da_nothing_rel_to = gl_str_da_inform_ti_nothing_relative_to.replace('$140', indexical)
                str_da_nothing_rel_to = str_da_nothing_rel_to.replace('$30', last_topic_field)
                da_nothing_rel_to = rp.parseDialogActFromString(str_da_nothing_rel_to)
                return ([ da_nothing_rel_to ], None)
    
    #handle "what are the middle numbers?"
    if num_name == 'digit':
        if grammatical_be == 'present-plural' or grammatical_be == 'past-plural':
            if indexical == 'first' or indexical == 'middle' or indexical == 'last':
                (segment_name, start_index_pointer, chunk_size) = findSegmentNameAndChunkSizeForIndexical(indexical)
                (ret_das, turn_topic) = handleSendSegmentChunkNameAndData(segment_name)
                return (ret_das, turn_topic)

    #handle "what is after that?" 
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_indexical_indicative, da_request_ti)
    if mapping != None:
        tell_who = mapping.get('50')
        indexical = mapping.get('140')
        indicative = mapping.get('100')
        if tell_who == 'tell-me':
            print 'A2 '
            rel = 0
            if indexical == 'previous':
                rel = -1
            elif indexical == 'next':
                rel = 1
            if rel != 0:
                last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
                last_topic_field = last_self_turn_topic.field_name
                print 'last_topic_field C: ' + str(last_topic_field)
                if last_topic_field == None:
                    last_digit_list = getDataValuesForDataIndices(last_self_turn_topic.data_index_list)
                    last_topic_field_list = findSegmentNameForDigitList(last_digit_list)
                    if len(last_topic_field_list) > 0:
                        last_topic_field = last_topic_field_list[0]
                print 'last_topic_field D: ' + str(last_topic_field)
                #try to return previous or next with respect to topic field
                if last_topic_field != None:
                    adjacent_field = getFieldRelativeToField(last_topic_field, rel)
                    print 'adjacent_field: ' + str(rel) + ' ' + str(adjacent_field)
                    if adjacent_field != None:
                        return handleSendSegmentChunkNameAndData(adjacent_field)
                    #nothing rel to last_topic_field
                    str_da_nothing_rel_to = gl_str_da_inform_ti_nothing_relative_to.replace('$140', indexical)
                    str_da_nothing_rel_to = str_da_nothing_rel_to.replace('$30', last_topic_field)
                    da_nothing_rel_to = rp.parseDialogActFromString(str_da_nothing_rel_to)
                    return ([ da_nothing_rel_to ], None)

                #if that fails, then return previous or next with respect to digit index
                else:
                    last_topic_index0 = last_self_turn_topic.data_index_list[0]
                    if last_topic_index0 >= 0:
                        target_digit_ith = last_topic_index0 + rel
                        target_digit_i = getDigitIndexForFieldRelativeIndex('telephone-number', target_digit_ith)
                        print 'target_digit_i: ' + str(target_digit_i)
                        if target_digit_i < 0:
                            str_da_nothing_rel_to_indicative = gl_str_da_inform_ti_nothing_relative_to_indicative.replace('$140', indexical)
                            da_nothing_rel_to_indicative = rp.parseDialogActFromString(str_da_nothing_rel_to_indicative)
                            return ([ da_nothing_rel_to_indicative ], None)
                        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[target_digit_i]
                        data_value_tuple = digit_belief.getHighestConfidenceValue()
                        digit_value = data_value_tuple[0]
                        digit_lf = synthesizeLogicalFormForDigitOrDigitSequence([digit_value])
                        turn_topic = TurnTopic()
                        turn_topic.data_index_list = [target_digit_i]
                        return ( [digit_lf], turn_topic)

                    
    #handle 'User: take this phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_you_phone_number, da_request_ti)
    if mapping != None:
        gl_agent.setRole('receive')
        gl_agent.setControl('partner')      #partner will drive this task
        return ([gl_da_affirmation_okay, gl_da_self_ready], None)    #XX need to fill in the turn_topic


    #handle "is/was six five zero the area code"
    #gl_str_da_is_digits_2_the_field = 'RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2)), FieldName($30))'
    mapping = None
    mapping_1 = rp.recursivelyMapDialogRule(gl_da_is_digits_1_the_field, da_request_ti)
    mapping_2 = rp.recursivelyMapDialogRule(gl_da_is_digits_2_the_field, da_request_ti)
    mapping_3 = rp.recursivelyMapDialogRule(gl_da_is_digits_3_the_field, da_request_ti)
    mapping_4 = rp.recursivelyMapDialogRule(gl_da_is_digits_4_the_field, da_request_ti)
    if mapping_4 != None and len(mapping_4) >= 5:
        mapping = mapping_4
        data_value_list = [mapping.get('1'), mapping.get('2'), mapping.get('3'), mapping.get('4')]
        field_name = mapping.get('30')
    elif mapping_3 != None and len(mapping_3) >= 4:
        mapping = mapping_3
        data_value_list = [mapping.get('1'), mapping.get('2'), mapping.get('3')]
        field_name = mapping.get('30')
    elif mapping_2 != None and len(mapping_2) >= 3:
        mapping = mapping_2
        data_value_list = [mapping.get('1'), mapping.get('2')]
        field_name = mapping.get('30')
    elif mapping_1 != None and len(mapping_1) >= 2:
        mapping = mapping_1
        data_value_list = [mapping.get('1')]
        field_name = mapping.get('30')
    if mapping != None:
        #First try to reply with the actual segment name for the digits spoken by partner
        print 'data_value_list: ' + str(data_value_list)

        actual_segment_names = findSegmentNameForDigitList(data_value_list)
        if len(actual_segment_names) > 0:
            #really we should allow multiple segment names with the same digit sequence
            actual_segment_name = actual_segment_names[0]

            #str_da_say_actual_segment_name_is = gl_str_da_say_field_is.replace('$30', actual_segment_name)
            #da_say_actual_segment_name_is = rp.parseDialogActFromString(str_da_say_actual_segment_name_is)
            segment_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
            str_da_inform_be_indicative = gl_str_da_inform_be_indicative.replace('$100', 'definite-present')
            da_inform_be_indicative = rp.parseDialogActFromString(str_da_inform_be_indicative)
            str_da_actual_field_name = gl_str_da_field_name.replace('$30', actual_segment_name)
            da_actual_field_name = rp.parseDialogActFromString(str_da_actual_field_name)

            turn_topic = TurnTopic()
            turn_topic.field_name = actual_segment_name
            turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
            gl_agent.setControl('partner')      #partner has taken control
            if actual_segment_name == field_name:
                #more syntax than I would prefer
                ret_das = [ gl_da_affirmation_yes, segment_digit_sequence_lf, da_inform_be_indicative, da_actual_field_name]
                print 'ret_das: ' + str(ret_das)
                return (ret_das, turn_topic)
            else:
                ret_das = [ gl_da_correction_dm_negation, segment_digit_sequence_lf, da_inform_be_indicative, da_actual_field_name]
                print 'ret_das: ' + str(ret_das)
                return (ret_das, turn_topic) 

        #If that fails, then report on the correct digits of the segment named by partner in their query.
        str_da_say_field_is = gl_str_da_say_field_is.replace('$30', field_name)
        da_say_field_is = rp.parseDialogActFromString(str_da_say_field_is)
        field_data_value_list = getDataValueListForField(gl_agent.self_dialog_model.data_model, field_name)
        field_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(field_data_value_list)
        turn_topic = TurnTopic()
        turn_topic.field_name = field_name
        turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, field_name)
        gl_agent.setControl('partner')      #partner has taken control
        if data_value_list == field_data_value_list:
            print ' returning affirmation yes ' + str(field_data_value_list)
            ret_das = [ gl_da_affirmation_yes, da_say_field_is]
            if field_digit_sequence_lf != None:
                ret_das.append(field_digit_sequence_lf)
            return (ret_das, turn_topic)
        else:
            print ' returning correction negation ' + str(field_data_value_list)
            ret_das = [ gl_da_correction_dm_negation, da_say_field_is]
            if field_digit_sequence_lf != None:
                ret_das.append(field_digit_sequence_lf)
            print 'ret_das: ' + str(ret_das)
            return (ret_das, turn_topic)

    #print 'MMM'

    #handle "is the area code six five zero?"
    #gl_str_da_request_confirm_field = 'RequestTopicInfo(request-confirmation, Tense($100), FieldName($30))')
    mapping = None
    mapping = rp.recursivelyMapDialogRule(gl_da_request_confirm_field, da_request_ti)
    if mapping != None:
        field_name = mapping.get('30')
        correct_field_data_value_list = getDataValueListForField(gl_agent.self_dialog_model.data_model, field_name)
        data_value_list = collectDataValuesFromDialogActs(da_list)

        str_da_say_field_is = gl_str_da_say_field_is.replace('$30', field_name)
        da_say_field_is = rp.parseDialogActFromString(str_da_say_field_is)
        field_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(correct_field_data_value_list)
        turn_topic = TurnTopic()
        turn_topic.field_name = field_name
        turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, field_name)
        gl_agent.setControl('partner')      #partner has taken control

        if data_value_list == correct_field_data_value_list:
            print ' returning affirmation yes ' + str(data_value_list)
            ret_das = [ gl_da_affirmation_yes, da_say_field_is]
            if field_digit_sequence_lf != None:
                ret_das.append(field_digit_sequence_lf)
            return (ret_das, turn_topic)
        else:
            print ' returning correction negation ' + str(data_value_list)
            ret_das = [ gl_da_correction_dm_negation, da_say_field_is]
            if field_digit_sequence_lf != None:
                ret_das.append(field_digit_sequence_lf)
            print 'ret_das: ' + str(ret_das)
            return (ret_das, turn_topic)



    #very similar to how we handle InformTopicInfo of one or more data items
    #gl_str_da_request_confirmation_ = 'RequestTopicInfo(request-confirmation'
    #str_da_rti = da_request_ti.getPrintString()
    #if str_da_rti.find(gl_str_da_request_confirmation_) == 0:
    #    return handleRequestTopicInfo_RequestConfirmation(da_list)

    #handle "User: was that seven two six", "six two seven right?" 
    for da in da_list:
        str_da = da.getPrintString()
        if str_da.find(gl_str_da_request_confirmation_) == 0:
            return handleRequestTopicInfo_RequestConfirmation(da_list)

    #handle "what is six five zero"
    data_value_list = collectDataValuesFromDialogActs(da_list)
    if len(data_value_list) > 0:
        (partner_expresses_confusion_p, last_topic_data_indices_matched_list, actual_segment_name, partner_digit_word_sequence) = \
                                     comparePartnerReportedDataAgainstSelfData(da_list)
        if actual_segment_name != None:
            str_da_say_is_field = gl_str_da_request_confirm_field.replace('$100', 'definite-present')
            str_da_say_is_field = str_da_say_is_field.replace('$30', actual_segment_name)
            da_say_is_field = rp.parseDialogActFromString(str_da_say_is_field)
            field_digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(partner_digit_word_sequence)
            ret_das = [ field_digit_sequence_lf, da_say_is_field ]
            turn_topic = TurnTopic()
            turn_topic.field_name = actual_segment_name
            turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, actual_segment_name)
            gl_agent.setControl('partner')      #partner has taken control
            return (ret_das, turn_topic) 

    print 'handleRequestTopicInfo_SendRole has no handler for request ' + da_request_ti.getPrintString()
    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    return (ret_das, None)    #XX need to fill in the turn_topic




#handle info receiver:  "was that seven two six?"
#borrows from handleInformTopicInfo_SendRole which covers for handleCheckTopicInfo_SendRole
#The main difference here is that the reply assumes the speaker requesting confirmation has
#low confidence in the information, so this gives the Topic Info Receiver a chance to 
#confirm or ask further questions. So, this increases confidence that the TIR has the
#correct data, but does not move on to the next segment.
#The Topic Info Receiver retains control.
def handleRequestTopicInfo_RequestConfirmation(da_list):
    global gl_agent
    global gl_most_recent_data_topic_da_list

    print 'handleRequestTopicInfo_RequestConfirmation '
    #printAgentBeliefs()

    (partner_expresses_confusion_p, last_topic_data_indices_matched_list, actual_segment_name, partner_digit_word_sequence) = \
                        comparePartnerReportedDataAgainstSelfData(da_list)

    #This is an easy out, to be made more sophisticated later
    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret_das = [gl_da_inform_dm_repeat_intention]
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        last_self_utterance_da_list = last_self_utterance_tup[2]
        #don't repeat repeat_intention
        last_self_utterance_da_list = stripDialogActsOfType(last_self_utterance_da_list, [ gl_str_da_inform_dm_repeat_intention ])  
        last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
        ret_das.extend(last_self_utterance_da_list)
        gl_agent.setControl('partner')      #partner has taken control by requesting confirmation
        return (ret_das, last_self_turn_topic)
    
    #Only if check-confirm match was validated against self's belief model, update self's model
    #for what partner believes about the data.
    if len(last_topic_data_indices_matched_list) > 0:
        possiblyAdjustChunkSize(len(last_topic_data_indices_matched_list))
        #1.0 is full confidence that the partner's data belief is as self heard it
        partner_dm = gl_agent.partner_dialog_model
        newly_matched_digits = []
        for digit_i in last_topic_data_indices_matched_list:
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, 1.0)
        #printAgentBeliefs()
        #since this was a request about data but has not been confirmed, don't advance self index pointer
        #middle_or_at_end = advanceSelfIndexPointer(gl_agent, match_count)  
        #print 'after advanceSelfIndexPointer...'
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

        #since this was a request, don't move on with the next chunk, just issue confirmation
        #and a reiteration of what data was confirmed
        ret_das = [gl_da_affirmation_yes]
        #substitute InformTopicInfo for RequestTopicInfo of the gl_most_recent_data_topic_list
        data_value_list = collectDataValuesFromDialogActs(gl_most_recent_data_topic_da_list)
        print 'data_value_list: ' + str(data_value_list)
            
        if len(data_value_list) >= 1:
            inform_digits_da = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
            if inform_digits_da != None:
                ret_das.append(inform_digits_da)
            #ret.extend(gl_most_recent_data_topic_da_list)
            gl_agent.setControl('partner')      #partner has taken control by requesting confirmation
            return (ret_das, None)     #XX need to fill in the turn_topic

    #since we haven't advanced the self data index pointer, then actually we are re-sending the 
    #previous chunk. 
    #Issue polite correction to the request: "sorry no it's"
    #Issue correction to the request: "no it's"
    ret_das = [ gl_da_correction_topic_info ]
    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    last_self_utterance_da_list = last_self_utterance_tup[2]
    #if the field name was said in the last utterance, say "no"
    #if the field name was not said in the last utterance, say "no it's"
    field_name_stated_p = False
    for da in last_self_utterance_da_list:
        mapping = rp.recursivelyMapDialogRule(gl_da_say_field_is, da)
        if mapping != None:
            field_name_stated_p = True
            break
    if field_name_stated_p:
        ret_das = [ gl_da_correction_dm_negation ]
    else: 
        ret_das = [ gl_da_correction_topic_info ]
    #don't repeat repeat_intention
    last_self_utterance_da_list = stripDialogActsOfType(last_self_utterance_da_list,\
                                                        [ gl_str_da_inform_dm_repeat_intention, gl_str_da_correction_topic_info, \
                                                          gl_str_da_affirmation_yes ])
    last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
    ret_das.extend(last_self_utterance_da_list)
    gl_agent.setControl('partner')      #partner has taken control by requesting confirmation
    return (ret_das, last_self_turn_topic)



def handleRequestTopicInfo_ReceiveRole(da_list):
    print 'handleRequestTopicInfo_ReceiveRole not written yet'
    return None


def handleRequestTopicInfo_BanterRole(da_list):
    print 'handleRequestTopicInfo_BanterRole da_list: '
    for da in da_list:
        print '    ' + da.getPrintString()

    da_request_ti = da_list[0]
    str_da_request_ti = da_request_ti.getPrintString()

    #"receive" and "send" are valid answers to a pending invitation
    if str_da_request_ti in [gl_str_da_receive, gl_str_da_send]:
        (ret_das, turn_tuple) = handleAnyPendingQuestion(da_list)
        if ret_das != None:
            return (ret_das, turn_tuple)

    clearPendingQuestions()

    #handled in handleRequestTopicInfo, not particular to BanterRole
    #handle 'User: what is your name'
    #rp.setTellMap(True)
    #mapping = rp.recursivelyMapDialogRule(gl_da_what_is_your_name, da_request_ti)
    #print 'mapping: ' + str(mapping)
    #if mapping != None:
    #    str_da_my_name_is = gl_str_da_agent_my_name_is.replace('$40', gl_agent.name)
    #    da_my_name_is = rp.parseDialogActFromString(str_da_my_name_is)
    #    return ([da_my_name_is], None)   #XX need to fill in the turn_topic

    #handle 'User: what is my name'
    #mapping = rp.recursivelyMapDialogRule(gl_da_what_is_my_name, da_request_ti)
    #gl_agent.setControl('partner')   #user is driving 
    #if mapping != None:

    #    str_da_agent_belief_yes = gl_str_da_agent_belief_yes
    #    da_agent_belief_yes = rp.parseDialogActFromString(str_da_agent_belief_yes)
    #    str_da_your_name_is = gl_str_da_your_name_is.replace('$40', gl_agent.partner_name)
    #    da_your_name_is = rp.parseDialogActFromString(str_da_your_name_is)
    #    return ([da_agent_belief_yes, da_your_name_is], None)   #XX need to fill in the turn_topic

    #handle 'User: send me the phone number'
    #rp.setTellMap(True)
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_phone_number, da_request_ti)
    if mapping != None:
        gl_agent.setRole('send', gl_default_phone_number)
        #it would be best to spawn another thread to wait a beat then start the
        #data transmission process, but return okay immediately.
        #do that later
        initializeStatesToSendPhoneNumberData(gl_agent)
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ da_segment_name ]
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
        ret_das.extend(data_chunk_das)
        gl_agent.setControl('self')      #start the main task, putting the computer agent in control
        return (ret_das, turn_topic)


    #handle "User: what is the area code"
    #handle "User: tell me the area code"
    field_name = None
    indexical = None
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field, da_request_ti)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_grammar, da_request_ti)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_indexical, da_request_ti)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_field_indexical_grammar, da_request_ti)
    if mapping != None:
        field_name = mapping.get('30')
        indexical = mapping.get('140')
    #handle "User: tell me the number"  
    #"number" can mean digit or telephone number. Here, the utterance does not include an indexical
    #like "third number", so we interpret it as the telephone number
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char, da_request_ti)
        if mapping == None:
            mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_grammar, da_request_ti)
        if mapping == None:
            mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_indexical, da_request_ti)
        if mapping == None:
            mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_item_type_char_indexical_grammar, da_request_ti)
        if mapping != None:
            indexical = mapping.get('140')
            num_name = mapping.get('25')
            if num_name == 'digit':
                field_name = 'telephone-number'
    if field_name == 'telephone-number':
        print ' banter role indexical: ' + str(indexical)
        gl_agent.setRole('send', gl_default_phone_number)
        initializeStatesToSendPhoneNumberData(gl_agent)
        if indexical == 'entire':
            chunk_size = getChunkSizeForSegment('telephone-number')
            possiblyAdjustChunkSize(chunk_size)
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ da_segment_name ]
        #start with area code segment but use entire telephone number chunk size if 'entire' was used
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', False)
        ret_das.extend(data_chunk_das)
        gl_agent.setControl('self')      #start the main task, putting the computer agent in control
        return (ret_das, turn_topic)

    #handle 'User: take this phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_you_phone_number, da_request_ti)
    if mapping != None:
        gl_agent.setRole('receive')
        return ([gl_da_affirmation_okay, gl_da_self_ready], None)   #XX need to fill in the turn_topic

    #handle "User: was that seven two six"
    #very similar to how we handle InformTopicInfo of one or more data items
    str_da_rti = da_request_ti.getPrintString()
    if str_da_rti.find(gl_str_da_request_confirmation_) == 0:
        gl_agent.setControl('partner')      #user asks a question so takes control
        return handleRequestTopicInfo_RequestConfirmation(da_list)

    print 'handleRequestTopicInfo_BanterRole has no handler for request ' + da_request_ti.getPrintString()
    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    return (ret_das, None)   #XX need to fill in the turn_topic









#RequestDialogManagement
#Request information about dialog management, or request adjustment in dialog management protocol.
#
def handleRequestDialogManagement(da_list):
    global gl_agent
    global gl_most_recent_data_topic_da_list
    da_request_dm = da_list[0] 
    str_da_request_dm = da_request_dm.getPrintString()

    print 'handleRequestDialogManagement()'
    for da in da_list:
        print '    ' + da.getPrintString()

    clearPendingQuestions()

    #handle readiness issues
    (ret_das, turn_topic) = handleReadinessIssues(da_list)
    if ret_das != None:
        print 'handleReadienssIssues returned ' + str(ret_das)
        for da in ret_das:
            print da.getPrintString()
        gl_agent.setControl('self')      #user asks a question so takes control
        return (ret_das, turn_topic) 

    #handle confusion issues
    (ret_das, turn_topic) = handleConfusionIssues(da_list)
    if ret_das != None:
        print 'handleConfusionIssues returned ' + str(ret_das)
        for da in ret_das:
            print da.getPrintString()
        gl_agent.setControl('self')      #user asks a question so takes control
        return (ret_das, turn_topic) 

    #handle chunk size issues
    for da in da_list:
        str_da = da.getPrintString()
        speed_or_slow_p = False
        if str_da.find(gl_str_da_request_dm_speed_slower) >= 0:
            (max_value, max_conf), (second_max_value, second_max_conf) =\
                       gl_agent.partner_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
            print 'HHHHere reduce chunk size from ' + str(max_value) + ', ' + str(second_max_value)
            speed_or_slow_p = True
            adjustChunkSize('decrease')
        if str_da.find(gl_str_da_request_dm_speed_faster) >= 0:
            (max_value, max_conf), (second_max_value, second_max_conf) =\
                       gl_agent.partner_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
            print 'HHHHere increase chunk size from ' + str(max_value) + ', ' + str(second_max_value)
            speed_or_slow_p = True
            adjustChunkSize('increase')
        if speed_or_slow_p and len(da_list) == 1:
            synth_repeat_da_list = [ gl_da_misalignment_request_repeat ]
            return handleRequestDialogManagement(synth_repeat_da_list)

    #handle "go on" effective Confirmation continuers
    if str_da_request_dm == gl_str_da_request_dm_proceed_with_next:
        synth_confirm_da_list = [ gl_da_affirmation_yes ]
        synth_confirm_da_list.extend( da_list[1:] )
        return handleConfirmDialogManagement_SendRole(synth_confirm_da_list, True)  #force declare? I guess

    #Determine if the utterance from partner merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_list:
        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_list[:]

    if str_da_request_dm == gl_str_da_request_dm_stop_process:
        stopMainLoop()
        gl_agent.setControl('partner')
        return ([gl_da_affirmation_okay ], None) 

    #handle restart 'let's start again'
    if str_da_request_dm == gl_str_da_misalignment_start_again:
        #sometimes a user will say "let's start again" after we're all done and back in banter role
        if gl_agent.send_receive_role == 'banter':
            gl_agent.setRole('send', gl_default_phone_number)
        if gl_agent.send_receive_role == 'send':
            initializeStatesToSendPhoneNumberData(gl_agent)
            str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
            da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
            ret_das = [ da_segment_name ]
            (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
            ret_das.extend(data_chunk_das)
            gl_agent.setControl('self')      #start the main task, putting the computer agent in control
            return (ret_das, turn_topic)
            
    #handle what was it again?   pronoun_ref, repeat the last utterance containing topic info
    if str_da_request_dm == gl_str_da_misalignment_request_repeat_pronoun_ref:
        #print ' fetch InformTopicInfo'
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        if last_self_utterance_tup != None:
            last_self_utterance_das = last_self_utterance_tup[2]
            last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
            return (last_self_utterance_das_stripped, None)   #XX need to fill in the turn_topic?

    #This is now under InformDialogManagement because it is not explicitly a request
    #handle   I did not get that
    #if str_da_request_dm == gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref: 
    #    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    #    if last_self_utterance_tup != None:
    #        last_self_utterance_das = last_self_utterance_tup[2]
    #        last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
    #        return last_self_utterance_das_stripped


    #handle "repeat that", "what did you say?"   no pronoun ref so repeat the last utterance
    if str_da_request_dm == gl_str_da_misalignment_request_repeat:
        #sometimes a user will say "repeat the phone number" after we're all done and back in banter role
        if gl_agent.send_receive_role == 'banter':   
            gl_agent.setRole('send', gl_default_phone_number)
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        print 'last_self_utterance_tup: ' + str(last_self_utterance_tup)
        if last_self_utterance_tup != None:
            last_self_utterance_das = last_self_utterance_tup[2]
            last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
            gl_agent.setControl('partner')    #user takes control to gain clarification
            return (last_self_utterance_das_stripped, None)   #XX need to fill in the turn_topic?


    #handle what did you say?  no pronoun ref, so just repeat the last utterance
    #if str_da_request_dm == gl_str_da_misalignment_self_hearing_or_understanding:
    #    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
    #    if last_self_utterance_tup != None:
    #        last_self_utterance_das = last_self_utterance_tup[2]
    #        #A judgement call here whether to strip off an initial confirmation or correction
    #        #For "what?" let's repeat the full statement literally.
    #        #last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
    #        #return last_self_utterance_das_stripped
    #        return last_self_utterance_das

    #handle "repeat the area code, etc'
    mapping = None
    mapping = rp.recursivelyMapDialogRule(gl_da_misalignment_request_repeat_field, da_request_dm)
    if mapping != None:
        #sometimes a user will say "repeat the phone number" after we're all done and back in banter role
        if gl_agent.send_receive_role == 'banter':   
            gl_agent.setRole('send', gl_default_phone_number)
        misunderstood_field_name = mapping.get('30')
        if misunderstood_field_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
            #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
            chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(misunderstood_field_name)
            for i in range(chunk_indices[0], chunk_indices[1] + 1):
                data_index_pointer = gl_10_digit_index_list[i]
                gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
            gl_agent.setControl('partner')    #user takes control
            #if the user says repeat the phone number, then don't send the whole thing at once
            print 'misunderstood_field_name: ' + misunderstood_field_name
            if misunderstood_field_name == 'telephone-number':
                initializeStatesToSendPhoneNumberData(gl_agent)
                str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
                da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
                ret_das = [ da_segment_name ]
                (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
                ret_das.extend(data_chunk_das)
                gl_agent.setControl('self')      #start the main task, putting the computer agent in control
                return (ret_das, turn_topic)
            return handleSendSegmentChunkNameAndData(misunderstood_field_name)

    #handle "is/was that the area code?"
    mapping = rp.recursivelyMapDialogRule(gl_da_request_clarification_utterance_field, da_request_dm)
    print 'mapping: ' + str(mapping)
    if mapping != None:
        clarification_grammar = mapping.get('100')
        clarification_field_name = mapping.get('30')
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        da_list = last_self_utterance_tup[2]
        segment_names = findSegmentNameForDialogActs(da_list)
        print 'segment_names: ' + str(segment_names)

        #yes, six five zero is the area code
        if len(segment_names) == 1 and segment_names[0] == clarification_field_name:
            digit_value_list = collectDataValuesFromDialogActs(da_list)
            digit_value_da = synthesizeLogicalFormForDigitOrDigitSequence(digit_value_list)
            da_str_inform_field = gl_str_da_inform_field.replace('$100', 'definite-present') # Tense($1)
            da_str_inform_field = da_str_inform_field.replace('$30', segment_names[0])      # FieldName($2)
            da_inform_field = rp.parseDialogActFromString(da_str_inform_field)
            turn_topic = TurnTopic()
            turn_topic.field_name = clarification_field_name
            turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, clarification_field_name)
            gl_agent.setControl('partner')    #user takes control 
            return ([gl_da_affirmation_yes, digit_value_da, da_inform_field], turn_topic) 
        #generate correction, 'no, [six five zero] is the [exchange]'
        elif len(segment_names) == 1:
            digit_value_list = collectDataValuesFromDialogActs(da_list)
            digit_value_da = synthesizeLogicalFormForDigitOrDigitSequence(digit_value_list)
            da_str_inform_field = gl_str_da_inform_field.replace('$100', 'definite-present') # Tense($1)
            da_str_inform_field = da_str_inform_field.replace('$30', segment_names[0])      # FieldName($2)
            da_inform_field = rp.parseDialogActFromString(da_str_inform_field)
            turn_topic = TurnTopic()
            turn_topic.field_name = segment_names[0]
            turn_topic.data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, segment_names[0])
            gl_agent.setControl('partner')    #user takes control 
            return ([gl_da_correction_dm_negation, digit_value_da, da_inform_field], turn_topic)

        #no, six two is not the area code
        digit_value_list = collectDataValuesFromDialogActs(da_list)
        digit_value_da = synthesizeLogicalFormForDigitOrDigitSequence(digit_value_list)
        str_da_not_field = gl_str_da_not_field.replace('$30', clarification_field_name)
        da_not_field = rp.parseDialogActFromString(str_da_not_field)
        turn_topic = TurnTopic()
        turn_topic.field_name = clarification_field_name
        gl_agent.setControl('partner')    #user takes control 
        return ([ gl_da_correction_dm_negation, digit_value_da, da_not_field ], turn_topic)


    #handle "User: did you say seven two six"
    #very similar to how we handle InformTopicInfo of one or more data items
    #gl_str_da_request_dm_clarification_utterance_ = 'RequestDialogManagement(clarification-utterance'
    #Put this later because it matches any remaining 'RequestDialogManagement(clarification-utterance'
    if str_da_request_dm.find(gl_str_da_request_dm_clarification_utterance_) == 0:
        #Even though this is a slightly different utterance, 'did you say $1' instead of 
        #'was that $1', we can handle it in the same way as a request for confirmation of data.
        gl_agent.setControl('partner')    #user takes control 
        return handleRequestTopicInfo_RequestConfirmation(da_list)


    #handle "what?"      not a pronoun ref so just repeat the last utterance, but only do so if there were not too many
    #other dialog acts stacked up, which means that we didn't understand what was being asked
    global gl_num_dialog_acts_following_what_indicating_confusion
    if str_da_request_dm == gl_str_da_what:
        if len(da_list)-1 < gl_num_dialog_acts_following_what_indicating_confusion:
            last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
            if last_self_utterance_tup != None:
                last_self_utterance_das = last_self_utterance_tup[2]
                last_self_utterance_das_stripped = possiblyStripLeadingDialogAct(last_self_utterance_das, 'confirmation-or-correction')
                gl_agent.setControl('partner')    #user takes control to gain clarification
                print 'len(da_list)-1 ' + str(len(da_list)-1) + ' < ' + str(gl_num_dialog_acts_following_what_indicating_confusion) + \
                    'so returning CCD'
                return (last_self_utterance_das_stripped, None)  #XX need to fill in the turn_topic?
        #too many dialog acts after what?, so we're confused
        else:
            print 'len(da_list)-1 ' + str(len(da_list)-1) + ' >= ' + str(gl_num_dialog_acts_following_what_indicating_confusion) + \
                'so returning CCE'
            ret_das = [ gl_da_i_heard_you_say ]
            ret_das.extend(da_list)
            ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
            return ( ret_das, None )


    #"what is the rest of the telephone number"
    print 'trying mapping '
    print ' A: ' + gl_da_request_dm_proceed_to_completion.getPrintString()
    print ' B: ' + da_request_dm.getPrintString()
    mapping = rp.recursivelyMapDialogRule(gl_da_request_dm_proceed_to_completion, da_request_dm)
    if mapping != None:
        print 'mapped  what is the rest of the telephone number?'
        field_name = mapping.get('30')  #Not really using this
        gl_agent.setControl('self')    #gl_agent retains or regains control
        last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
        turn_topic_data_index_list = last_self_turn_topic.data_index_list
        last_data_index = turn_topic_data_index_list[len(turn_topic_data_index_list)-1]
        next_data_index = last_data_index + 1
        (ret_das, turn_topic) = prepareNextDataChunk(next_data_index)
        updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
        return (ret_das, turn_topic)
        

    print 'handleRequestDialogManagement dropped through' 
    for da in da_list:
        print '    ' + da.getPrintString()

    print 'handleRequestDialogManagement has no handler for request ' + da_request_dm.getPrintString()
    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    return (ret_das, None)





gl_num_dialog_acts_following_what_indicating_confusion = 2


#Returns a tuple (da_list, turn_topic) if the input is about readiness, (None, None) if not
def handleReadinessIssues(da_list):
    global gl_agent
    da0 = da_list[0]
    
    print 'handleReadinessIssues da_list: ' + str(len(da_list))
    for da in da_list:
        print '   ' + da.getPrintString()

    #printTurnHistory()

    #handle not-readiness request and inform, "please wait", "i'm not ready"
    mapping = rp.recursivelyMapDialogRule(gl_da_request_self_not_ready, da0)
    if mapping == None:
        mapping = rp.recursivelyMapDialogRule(gl_da_inform_self_not_ready, da0)
    if mapping != None:
        gl_agent.partner_dialog_model.readiness.setBeliefInTrue(0)
        print 'reply okay ill wait'
        gl_agent.setControl('partner')    #user gets control 
        return ([ gl_da_affirmation_okay, gl_da_dm_confirm_partner_not_ready ], None)   #XX need to fill in the turn_topic

    #handle readiness continuer, "go on", "i'm ready now"
    #for now, just repeat what was said before about the topic
    #mapping = rp.recursivelyMapDialogRule(gl_da_request_self_ready, da0)
    #if mapping == None:
    mapping = rp.recursivelyMapDialogRule(gl_da_inform_self_ready, da0)
    if mapping != None:
        gl_agent.partner_dialog_model.readiness.setBeliefInTrue(1)
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo', 'RequestTopicInfo' 'RequestDialogManagement' ])
        print '..saw ready now, last_self_utterance_tup: ' + str(last_self_utterance_tup)
        if last_self_utterance_tup == None:
            print 'reply None'
            return (None, None)
        ret_das = last_self_utterance_tup[2]
        print 'reply ' + str(ret_das)
        gl_agent.setControl('self')    #gl_agent regains control
        return (ret_das, None)   #XX need to fill in the turn_topic

    #handle readiness check "are you waiting"
    mapping = rp.recursivelyMapDialogRule(gl_da_request_are_you_waiting, da0)
    if mapping != None:
        da_list = [  gl_da_affirmation_yes, gl_da_self_waiting ]
        return (da_list, None)

    #handle #"what are you waiting for"
    mapping = rp.recursivelyMapDialogRule(gl_da_request_are_you_waiting, da0)
    if mapping != None:
        da_list = [ gl_da_affirmation_yes, gl_da_inform_declare_waiting_for_partner ]
        return (da_list, None)

    print 'handleReadinessIssues dropping through'
    return (None, None)





#Returns a da_list if the input is about being confused.
def handleConfusionIssues(da_list):
    global gl_agent
    da0 = da_list[0]
    str_da0 = da0.getPrintString()
    
    print 'handleConfusionIssues da_list: ' + str(len(da_list))
    if str_da0.find(gl_str_da_request_dm_misalignment_confusion) >= 0 or \
       str_da0.find(gl_str_da_inform_dm_misalignment_confusion) >= 0:

        gl_agent.setRole('send', gl_default_phone_number)
        initializeStatesToSendPhoneNumberData(gl_agent)
        str_da_say_telephone_number_is = gl_str_da_say_field_is.replace('$30', 'telephone-number')
        da_say_telephone_number_is = rp.parseDialogActFromString(str_da_say_telephone_number_is)
        str_da_segment_name = gl_str_da_field_name.replace('$30', 'area-code')
        da_segment_name = rp.parseDialogActFromString(str_da_segment_name)
        ret_das = [ gl_da_misalignment_start_again, da_say_telephone_number_is, da_segment_name ]
        (data_chunk_das, turn_topic) = initiateTopicAtSegmentAndPrepareDataChunk(gl_agent, 'area-code', True)
        ret_das.extend(data_chunk_das)
        return (ret_das, turn_topic)

    return (None, None)



                                                  

#da_list is a list of DialogActs
#Returns a list of data segment names (e.g. 'area-code') for the agent's self_dialog_model.data_model 
#that match the digits
def findSegmentNameForDialogActs(da_list):
    global gl_agent
    test_digit_value_list = collectDataValuesFromDialogActs(da_list)
    return findSegmentNameForDigitList(test_digit_value_list)



#da_list is a list of digit values, e.g. ['six', 'five', 'zero']
#Returns a list of data segment names (e.g. 'area-code') for the agent's self_dialog_model.data_model 
#that match the digits
def findSegmentNameForDigitList(digit_list):
    matching_segment_name_list = []

    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]

        print 'testing segment_name ' + segment_name
        test_digit_i = 0
        match_p = True
        for segment_i in range(segment_start_index, segment_end_index+1):
            if segment_end_index - segment_start_index + 1 != len(digit_list):
                match_p = False
                break
            segment_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[segment_i]
            segment_data_value_tuple = segment_digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            segment_data_value = segment_data_value_tuple[0]
            if test_digit_i >= len(digit_list):
                match_p = False
                break
            test_digit_value = digit_list[test_digit_i]
            if segment_data_value != test_digit_value:
                print 'XX segment_data_value ' + segment_data_value + ' != test_digit_value ' + test_digit_value
                match_p = False
                break
            elif segment_i == segment_end_index:
                if test_digit_i+1 < len(digit_list):
                    print 'test_digit_i ' + str(test_digit_i) + ' < ' + 'len(test_digit_value_list): ' + str(len(digit_list))
                    match_p = False
                break
            test_digit_i += 1
        if match_p:
            matching_segment_name_list.append(segment_name)
    print 'findSegmentNameForDigitList found segment names: ' + str(matching_segment_name_list)
    return matching_segment_name_list
        

    

    
#Runs through a list of DialogActs that might include InformTopicInfo(ItemValue( Digit or DigitSequence.
#Collects up all of the digits in order and returns them in a list.
#If even_non_inform_p is True, then this examimes all DialogActs in da_list
#If even-non_inform_p is False, then this first checks to see if da_list contains dialog acts that indicate
#not simply InformTopicInfo, but misalignment, confusion, or question
def collectDataValuesFromDialogActs(da_list, insert_qm_for_what_p=False):
    global gl_digit_list
    digit_value_list = []

    for da in da_list:
        str_da = da.getPrintString()
        ds_index = str_da.find('ItemValue(DigitSequence(')
        if ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = str_da.find(')', start_index)
            digit_value_list.extend(extractItemsFromCommaSeparatedListString(str_da[start_index:rp_index]))
            continue
        d_index = str_da.find('ItemValue(Digit(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = str_da.find(')', start_index)
            digit_value_list.append(str_da[start_index:rp_index])
            continue
        #If insert_qm_for_what_p is True, then if partner said "what" among digits, add ? partner utterance explicitly into 
        #the list of digits we heard them say, in order to pinpoint the index pointer for their indicated check-confusion.
        if str_da not in gl_digit_list and str_da.find('RequestDialogManagement(what)') == 0 and insert_qm_for_what_p:
            digit_value_list.append('?')
            continue
    return digit_value_list



    


#This sets the self and partner data_index_pointer to the start of the segment
#Returns a tuple: (list of dialog-acts which could be empty, turn_topic)
#If say_field_is_p is True, then this introduces the field with "the [field-name] is",
#If False, then simply [field-name]
def handleSendSegmentChunkNameAndData(segment_chunk_name, say_field_is_p=True):
    global gl_agent
    print 'handleSendSegmentChunkNameAndData(' + segment_chunk_name + ', ' + str(say_field_is_p) + ')'
    chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
    #This decision to reset belief in partner data_model now made by the caller.
    ##If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
    #for i in range(chunk_indices[0], chunk_indices[1] + 1):

    chunk_start_index = chunk_indices[0]
    
    if say_field_is_p:
        str_da_say_field_is = gl_str_da_say_field_is.replace('$30', segment_chunk_name)
        da_say_field_is = rp.parseDialogActFromString(str_da_say_field_is)
        ret_das = [da_say_field_is]
    else:
        str_da_field_name = gl_str_da_field_name.replace('$30', segment_chunk_name)
        da_field_name = rp.parseDialogActFromString(str_da_field_name)
        ret_das = [da_field_name]

    data_value_list = []
    data_index_list = []
    for digit_i in range(chunk_indices[0], chunk_indices[1]+1):
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
        data_index_list.append(digit_i)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        ret_das.append(digit_sequence_lf)
        turn_topic = TurnTopic()
        turn_topic.field_name = segment_chunk_name
        turn_topic.data_index_list = data_index_list
        return (ret_das, turn_topic)  
    else:
        return (None, None)




####
#
#Check
#
#Reiterate or request affirmation of topic information or dialog management protocol state.
#Assumption that the speaker's belief confidence is high.
#


#CheckTopicInfo
#Reiterate or solicit affirmation of topic information.
#
def handleCheckTopicInfo(da_list):
    print 'handleCheckTopicInfo not written yet'



#CheckDialogManagement
#Solicit request of affirmation of dialog management parameters and status.
#
def handleCheckDialogManagement(da_list):
    print 'handleCheckDialogManagement not written yet'


####
#
#Confirm
#
#Profide confirmation or affirmation of topic information or dialog management.
#Assumption that the speaker's belief confidence is high.
#Used if sender believes the recipient's information is correct.
#

#ConfirmTopicInfo
#Reiterate or affirm/disaffirm topic information.
#ConfirmTopicInfo will be used almost exclusively by the information sender.
#
def handleConfirmTopicInfo(da_list):
    print 'handleConfirmTopicInfo not written yet'



#The confidence the data sender places in the belief that the data receiver has the
#correct data, when the receiver does not check-confirm the data value, but only 
#issues a confirm-affirmation (e.g. "yes", "okay").
#This might be set according to estimate of channel quality and receiver understanding 
#reliability
gl_confidence_for_confirm_affirmation_of_data_value = .8

#The confidence the data sender places in the belief that the data receiver has the
#correct data, when they tell the data, but before they have gotten any confirmation
gl_confidence_in_partner_belief_for_tell_only = .2

#A threshold on confidence the data sender has that the belief that the data receiver has the
#correct data.   Below this confidence, double check that the receiver has really got it right.
gl_confidence_in_partner_belief_to_double_check = .5





#ConfirmDialogManagement
#Reiterate or affirm/disaffirm dialog management protocol state.
#
#[Also used if the speaker is the information recipient but is taking authoritative
# stance about and responsibility for their topic belief.]
def handleConfirmDialogManagement(da_list):
    global gl_agent
    da_confirm_dm = da_list[0]
    print 'handleConfirmDialogManagement'
    for da in da_list:
        print '    ' + da.getPrintString()

    #a confirmation indicates that partner is ready (unless the followup dialog acts say otherwise)
    gl_agent.partner_dialog_model.readiness.setBeliefInTrue(1) 

    #A ConfirmDialogManagement dialog act might be an answer to a pending question
    #Right now, only test the partner input is a single Confirm DialogAct.
    #This is not structured completely well.  If the user says, 
    #  A: "Would you like to send or receive a phone number"
    #  U: "Yes.  Tell me a phone number", 
    #then it is incorrect to respond with the full followup, "sorry I can only send"
    if len(da_list) == 1:
        (ret_das, turn_tuple) = handleAnyPendingQuestion(da_list)
        if ret_das != None:
            return (ret_das, turn_tuple)

    #printAgentBeliefs(False)
    print 'partner readiness: ' + str(gl_agent.partner_dialog_model.readiness.true_confidence)

    #if we've been waiting for partner to be ready, then this is a resumption, not approval to move on
    #for now, just repeat what was said before about the topic
    if gl_agent.partner_dialog_model.readiness.true_confidence < .5:
        gl_agent.partner_dialog_model.readiness.setBeliefInTrue(1)
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        if last_self_utterance_tup == None:
            return [ gl_da_affirmation_okay ]
        ret_das = last_self_utterance_tup[2]
        current_control = gl_agent.getCurrentControl()
        if current_control != 'self':
            print 'returning control to self A'
        gl_agent.setControl('self')    #gl_agent regains control
        return (ret_das, None)   #XX need to fill in the turn_topic

    #handle affirmation continuer: 'User: okay or User: yes
    #right now, we don't have any other kind of ConfirmDialogManagement
    mapping = rp.recursivelyMapDialogRule(gl_da_affirmation, da_confirm_dm)

    if mapping == None:
        return None
    if gl_agent.send_receive_role == 'banter':
        return handleConfirmDialogManagement_BanterRole(da_list)

    if gl_agent.send_receive_role == 'send':
        return handleConfirmDialogManagement_SendRole(da_list)

    if gl_agent.send_receive_role == 'receive':
        return handleConfirmDialogManagement_ReceiveRole(da_list)



#This is for when the data Topic Info Sender receives a ConfirmDialogManagement DialogAct from the topic info recipient,
#e.g. "okay"
#This allows the caller to pass force_declare_segment_name on to prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()
#If True, then if a set of dialog acts containing more data is return, their data indices will be sent as well.
#But this function is only called other than from generateResponseToInputDialog(user_da_list) by handleInformRoleInterpersonal()
def handleConfirmDialogManagement_SendRole(da_list, force_declare_segment_name_p=False):
    global gl_agent
    print 'handleConfirmDialogManagement_SendRole'
    for da in da_list:
        print '   ' + da.getPrintString()

    # here we need to detect any number in the da_list
    #if there is one, then strip off the initial confirm before it updateBeliefInPartnerDataState because
    #the number overrides the general affirmation and gets specific about what is being confirmed
        
    #In case the ConfirmDialogManagement DialogAct is compounded with other DialogActs on this turn,
    #then strip out the ConfirmDialogManagement DialogActs and call generateResponseToInputDialog again recursively.
    #Strip out all affirmations from the list of remaining DialogActs to avoid the mistake of calling
    #updateBeliefInPartner...on this partner turn, when the turn also contains details like a digit
    #being confirmed.
    #But, if there are no digits in the remaining dialog acts, then accept the initial Confirm as 
    #confirming just-sent topic info.
    da_list_no_confirm = []
    da_digit_list = collectDataValuesFromDialogActs(da_list)
    for da in da_list:
        str_da = da.getPrintString();
        if str_da.find('ConfirmDialogManagement') < 0:
            da_list_no_confirm.append(da)
    print 'len(da_list_no_confirm): ' + str(len(da_list_no_confirm)) + ' len(da_list): ' + str(len(da_list))
    if len(da_list_no_confirm) > 0:
        #if no digits are present in the remaining da_list_no_confirm, then call updateBeliefs...
        if len(da_digit_list) == 0:
            updateBeliefInPartnerDataStateBasedOnMostRecentTopicData(gl_confidence_for_confirm_affirmation_of_data_value)
        return generateResponseToInputDialog(da_list_no_confirm)

    #Determine whether the confirmation applies to a self InformTopicInfo sending digits
    #Treat this use dialog act as a conformation of digits only if we have just said some digits and there is 
    #no accompanying misunderstanding dialog act
    #Try to adjust chunk size per the last utterance, since ConfirmDialogManagement (e.g. "okay") was given for it.
    update_belief_p = True

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
    if last_self_utterance_tup != None:
        last_self_utterance_das = last_self_utterance_tup[2]

        for da in last_self_utterance_das:
            if da.getPrintString().find(gl_str_da_misalignment_any) >= 0:
                print 'handleConfirmDialogManagement sees that the last self utterance had a misalignment ' 
                update_belief_p = False
                break
                #print '   ' + da.getPrintString()
                #print ' returning None'
                #return None

        last_sent_digit_value_list = collectDataValuesFromDialogActs(last_self_utterance_das)
        if last_sent_digit_value_list == None or len(last_sent_digit_value_list) == 0:
            print 'handleConfirmDialogManagement sees that the last self utterance did not inform about data: '
            update_belief_p = False
            #for da in last_self_utterance_das:
            #    print '   ' + da.getPrintString()
            #print ' returning None'
            #return None
        else:
            possiblyAdjustChunkSize(len(last_sent_digit_value_list))

    if update_belief_p:
        updateBeliefInPartnerDataStateBasedOnMostRecentTopicData(gl_confidence_for_confirm_affirmation_of_data_value)

    (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

    if len(self_belief_partner_is_wrong_digit_indices) == 0 and len(self_belief_partner_registers_unknown_digit_indices) == 0:
        gl_agent.setRole('banter')
        return ([gl_da_all_done], None)    #XX need to fill in the turn_topic
    
    #In case the ConfirmDialogManagement DialogAct is compounded with other DialogActs on this turn,
    #call generateResponseToInputDialog again recursively.
    #Strip out all affirmations from the list of remaining DialogActs to avoid the mistake of calling
    #updateBeliefInPartner... above again on this partner turn.
    #This is not really the right way to handle multiple affirmations in an utterance.
    #Really, additional confirmations within the utterance should be doing reinforcement 
    #of the interpretation, not tacking on one after another.
    da_list_remainder = []
    for da in da_list:
        if da.intent != 'ConfirmDialogManagement':
            da_list_remainder.append(da)
    if len(da_list_remainder) > 0:
        return generateResponseToInputDialog(da_list_remainder)

    #handle "what's next" "go on"
    #If the confirmation is specifically to proceed from the last chunk, then prepare the data chunk
    #that follows it.  Here, we are not zeroing out partner's belief in this next chunk's data (if 
    #they had previously confirmed it).
    da0 = da_list[0]
    str_da0 = da0.getPrintString()
    if str_da0 == gl_da_request_dm_proceed_with_next:
        gl_agent.setControl('self')    #gl_agent retains or regains control
        last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
        turn_topic_data_index_list = last_self_turn_topic.data_index_list
        last_data_index = turn_topic_data_index_list[len(turn_topic_data_index_list)-1]
        next_data_index = last_data_index + 1
        (ret_das, turn_topic) = prepareNextDataChunk(next_data_index)
        updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
        return (ret_das, turn_topic)

    current_control = gl_agent.getCurrentControl()
    #complete the digits for the current topic before popping up to inform incorrect or unknown indices
    last_self_turn_topic = gl_agent.self_dialog_model.getLastTurnTopic()
    print 'last_self_turn_topic: ' + last_self_turn_topic.getPrintString()
    turn_topic_data_index_list = last_self_turn_topic.data_index_list
    last_data_index = turn_topic_data_index_list[len(turn_topic_data_index_list)-1]
    (ret_das, turn_topic) = prepareNextDataChunkToContinueSegment(last_data_index)
    if ret_das != None:
        updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
        return (ret_das, turn_topic)

    #Only regain control when done with the segment we were dealing with
    #$$XX This needs a better idea of when to declare topic index
    regaining_control_p = False
    if current_control != 'self':
        regaining_control_p = True
        print 'returning control to self B' 
    gl_agent.setControl('self')    #gl_agent regains control

    #Determine whether the next field chunk follows directly from the previous field.
    #If not, we'll need to state the field name.
    print 'CDM_SR calling prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()'
    ( data_ret_das, turn_topic ) = prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers(True)
    updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(data_ret_das, turn_topic, gl_confidence_in_partner_belief_for_tell_only)
    current_field_subsequent_to_previous_p = False
    print 'turn_topic.field_name: ' + str(turn_topic.field_name) + '  last_self_turn_topic.field_name: ' + str(last_self_turn_topic.field_name)
    if turn_topic.field_name != None and last_self_turn_topic.field_name != None:
        next_field = getFieldSubsequentToField(last_self_turn_topic.field_name)
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        #Only bypass stating the field name if this confirmation follows directly after self's previous utterance of the topic data
        if next_field == turn_topic.field_name and last_self_utterance_tup[0] == last_self_turn_topic.turn[0]:
            current_field_subsequent_to_previous_p = True
    ret_das = []
    if (turn_topic.field_name != None and current_field_subsequent_to_previous_p == False) or force_declare_segment_name_p:
        str_da_say_field_is = gl_str_da_say_field_is.replace('$30', turn_topic.field_name)
        da_say_field_is = rp.parseDialogActFromString(str_da_say_field_is)
        ret_das.append(da_say_field_is)
    ret_das.extend(data_ret_das)
    return (ret_das, turn_topic)


def handleConfirmDialogManagement_ReceiveRole(da_list):
    print 'handleConfirmDialogManagement_ReceiveRole'
    for da in da_list:
        print '   ' + da.getPrintString()
    return None



def handleConfirmDialogManagement_BanterRole(da_list):
    for da in da_list:
        print '   ' + da.getPrintString()

    #strip out any confirm DialogActs and pass on the rest to the top level handler
    da_list_no_confirm = []
    for da in da_list:
        str_da = da.getPrintString();
        if str_da.find('ConfirmDialogManagement') < 0:
            da_list_no_confirm.append(da)
    print 'len(da_list_no_confirm): ' + str(len(da_list_no_confirm)) + ' len(da_list): ' + str(len(da_list))
    if len(da_list_no_confirm) > 0:
        return generateResponseToInputDialog(da_list_no_confirm)

    #da_list contained only confirmations, no instructions.
    
    #here, just say Hello and reiterate the top level invitation
    #allow "yes" and "no"
    possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,\
                                               gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure,\
                                               gl_da_receive, gl_da_send)

    removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
    pushQuestionToPendingQuestionList(gl_turn_number, 'self', gl_da_request_dm_invitation_send_receive, 
                                      gl_str_da_request_dm_invitation_send_receive, (possible_answers_to_invitation_question))

    "Hello?  Would you like to send or recieve a telephone number?"
    return ([gl_da_misaligned_roles, gl_da_request_dm_invitation_send_receive], None)  #XX need to fill in the turn_topic






#Compares self and partner data_model beliefs, and prepares a next set of DialogActs to send,
#as well as a turn_topic.
#Under a normal send situation, the delta in data_model beliefs will be the partner holding unknown (?)
#data values for the next segment, as indicated by the consensus index pointer.
#If this is the case, then just the data of the next segment are queued up as DialogActs.
#If however partner's data_model has a high confidence conflict with self's, or if the 
#first unknown digit is not the start of the next consensus index pointer segment, then
#this prepares a sequence of DialogActs that calls out the segment name explicitly.
def prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers(reset_chunk_size_for_segment_p = False):
    global gl_agent
    (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

    print 'prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers'

    #Assume any wrong digits indices are in small-to-large order.
    #If something is wrong, then restate the entire segment.
    if len(self_belief_partner_is_wrong_digit_indices) > 0:
        data_index_of_focus = self_belief_partner_is_wrong_digit_indices[0]
        (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(data_index_of_focus)
        return handleSendSegmentChunkNameAndData(segment_name)

    #Assume the unknown digits are in small-to-large order.
    if len(self_belief_partner_registers_unknown_digit_indices) > 0:
        next_data_index = self_belief_partner_registers_unknown_digit_indices[0]
        #if force_declare_segment_name:
        #    (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(next_data_index)
        #    return handleSendSegmentChunkNameAndData(segment_name)
        return prepareNextDataChunk(next_data_index, reset_chunk_size_for_segment_p)
        
    #we're done actually
    gl_agent.setRole('banter')
    return ([gl_da_all_done], None)   #XX need to fill in the turn_topic



#last_digit_i is a confirmed digit index by partner 
#check what segment this occurs in.  If not at the end of that segment,
#prepare a da_list based on remaining digit indices in the segment, and chunk size
def prepareNextDataChunkToContinueSegment(last_digit_i):
    global gl_agent
    print 'prepareNextDataChunkToContinueSegment(' + str(last_digit_i) + ')'
    
    (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(last_digit_i)
    print '(' + segment_name + ', ' + str(segment_start_index) + ',' + str(chunk_size) + ')'
    segment_data_index_list = getDataIndexListForField(gl_agent.self_dialog_model.data_model, segment_name)
    if segment_data_index_list[len(segment_data_index_list)-1] == last_digit_i:
        print 'segment_data_index_list: ' + str(segment_data_index_list) + '[' + str(len(segment_data_index_list)-1) + '] =' + str(segment_data_index_list[len(segment_data_index_list)-1])
        return (None, None)
    print '  segment_data_index_list: ' + str(segment_data_index_list)

    next_digit_i = None
    for i in range(0, len(segment_data_index_list)):
        if last_digit_i == segment_data_index_list[i]:
            next_digit_i = segment_data_index_list[i+1]
            break;
        print ' last_digit_i: ' + str(last_digit_i) + ' != segment_data_index_list[' + str(i) + ']:' + str(segment_data_index_list[i])
    if next_digit_i == None:
        return (None, None)
    return prepareNextDataChunk(next_digit_i)




def getFieldSubsequentToField(field_name):
    global gl_agent

    field_indices = gl_agent.self_dialog_model.data_model.data_indices[field_name]
    field_last_index = field_indices[1]
    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        if field_last_index == segment_start_index - 1:
            return segment_name
    return None






#Returns a tuple (segment_name, start_index_pointer, chunk_size) for the data_pointer_index 
#value passed based on the agent's data_model.  The data_index_pointer passed could be in the
#middle of a chunk.
def findSegmentNameAndChunkSizeForDataIndex(data_index_pointer):
    global gl_agent
    smallest_fitting_segment_tuple_chunk_size = 100000
    smallest_fitting_segment_tuple = None
    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if data_index_pointer < segment_start_index:
            continue
        elif data_index_pointer > segment_end_index:
            continue
        else:
            chunk_size = segment_end_index - segment_start_index + 1
            if chunk_size < smallest_fitting_segment_tuple_chunk_size:
                smallest_fitting_segment_tuple_chunk_size = chunk_size
                smallest_fitting_segment_tuple = (segment_name, segment_start_index, chunk_size)
    print 'findSegmentNameAndChunkSizeForDataIndex(' + str(data_index_pointer) + ') finds smallest_fitting_segment_tuple: ' + str(smallest_fitting_segment_tuple)
    return smallest_fitting_segment_tuple



#Returns a tuple (segment_name, start_index_pointer, chunk_size) for the indexical passed, 
#one of {first, middle, last}
def findSegmentNameAndChunkSizeForIndexical(indexical):
    global gl_agent

    if indexical == 'first':
        segment_name = 'area-code'
    elif indexical == 'middle':
        segment_name = 'exchange'
    elif indexical == 'last':
        segment_name = 'line-number'

    segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
    segment_start_index = segment_indices[0]
    segment_end_index = segment_indices[1]
    chunk_size = segment_end_index - segment_start_index + 1
    smallest_fitting_segment_tuple_chunk_size = chunk_size
    smallest_fitting_segment_tuple = (segment_name, segment_start_index, chunk_size)
    return smallest_fitting_segment_tuple






#target_chunk_size is typically the number of digits sent as check digits by partner.
#This compares with the current chunk size and possibly adjusts it upward or downward.
#We keep the self_dialog_model.protocol_chunck_size aligned with what the partner is indicating.
def possiblyAdjustChunkSize(target_chunk_size):
    print 'possiblyAdjustChunkSize ' + str(target_chunk_size)
    global gl_agent
    (max_value, max_conf), (second_max_value, second_max_conf) =\
                               gl_agent.partner_dialog_model.protocol_chunk_size.getTwoMostDominantValues()

    #print str(((max_value, max_conf), (second_max_value, second_max_conf)))
    if target_chunk_size < max_value and target_chunk_size < second_max_value:
        #print '...setting to ' + str(target_chunk_size)
        gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)
        gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)

    #hardcode phone number area code and exchange chunk size of 3
    elif target_chunk_size == 3 or target_chunk_size == 4:
    #elif target_chunk_size > max_value and max_value < 3:
        #print '...setting to 3/4'
        gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
        gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
    else:
        gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)
        gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)
        print '...setting chunk_size to ' + str(target_chunk_size)


def adjustChunkSize(increase_or_decrease):
    global gl_agent
    print 'adjustChunkSize ' + increase_or_decrease

    (max_value, max_conf), (second_max_value, second_max_conf) =\
                               gl_agent.partner_dialog_model.protocol_chunk_size.getTwoMostDominantValues()

    print str(((max_value, max_conf), (second_max_value, second_max_conf)))
    target_chunk_size = -1
    if increase_or_decrease == 'increase':
        if max_value == 1:
            target_chunk_size = 3
        elif max_value == 3 or max_value == 4:
            target_chunk_size = 10
    elif increase_or_decrease == 'decrease':
        if max_value == 10:
            target_chunk_size = 3
        elif max_value == 3 or max_value == 4:
            target_chunk_size = 1
    if target_chunk_size > 0:
        possiblyAdjustChunkSize(target_chunk_size)



def getChunkSizeForSegment(segment_name):
    global gl_agent
    segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
    segment_start_index = segment_indices[0]
    segment_end_index = segment_indices[1]
    chunk_size = segment_end_index - segment_start_index + 1
    return chunk_size







####
#
#Correction
#
#Disaffirm topic information as communicated or dialog management protocol state.
#Assumption that that the recipient's belief confidence is high.
#Used if sender believes the recipient's information is incorrect.
#

#CorrectionTopicInfo
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionTopicInfo(da_list):
    print 'handleCorrectionTopicInfo checking for "no"'
    da0 = da_list[0]
    print da0.getPrintString()

    #A CorrectionDialogManagement dialog act might be an answer to a pending question
    #"no"
    if da0.getPrintString() == gl_str_da_correction_ti_negation:
        (ret_das, turn_tuple) = handleAnyPendingQuestion(da_list)
        if ret_das != None:
            return (ret_das, turn_tuple)
    
    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    gl_agent.setControl('self')     #agent takes control to make correction
    return (ret_das, None)  #XX need to fill in the turn_topic




#CorrectionDialogManagement
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionDialogManagement(da_list):
    print 'handleCorrectionDialogManagement nothing more to do yet'
    return None



####
#
#RequestAction
#
#Request robot action or speech
#Used for testing TTS
#

gl_home = expanduser("~")
#gl_tts_temp_file = 'C:/tmp/audio/gtts-out.wav'
#gl_tts_temp_file = 'C:/tmp/audio/gtts-out.mp3'
gl_tts_temp_file = os.path.join(gl_home, 'temp-gtts-out.mp3')



#RequestAction
#Reiterate or affirm/disaffirm topic information.
#
def handleRequestAction(da_list):
    da0 = da_list[0]
    print 'handleRequestAction'
    for da in da_list:
        print '    ' + da.getPrintString()

    clearPendingQuestions()

    if da0.getPrintString() == gl_str_da_request_action_echo:
        data_list = collectDataValuesFromDialogActs(da_list)
        
        tts_string = ' '.join(data_list)
        print 'tts_string: ' + tts_string
        ttsSpeakText(tts_string)





#
####
#
#################




def initializeStatesToSendPhoneNumberData(agent):
    #agent is ready
    agent.self_dialog_model.readiness.setBeliefInTrue(1) 
    #agent believes partner is ready
    agent.partner_dialog_model.readiness.setBeliefInTrue(1) 

    #agent believes it is his turn
    agent.self_dialog_model.turn.setAllConfidenceInOne('self')
    #agent believes partner believes it is the agent's turn
    agent.partner_dialog_model.turn.setAllConfidenceInOne('self')

    #initialize with chunk size 3/4
    agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)     
    #agent believes the partner is ready for chunk size 3/4
    agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)     

    #initialize with moderate handshaking
    agent.self_dialog_model.protocol_handshaking.setAllConfidenceInOne(3)  
    #agent believes the partner is ready for moderate handshaking
    agent.partner_dialog_model.protocol_handshaking.setAllConfidenceInOne(3)  

    agent.partner_dialog_model.data_model.resetUnknownDigitValues()






#Returns a tuple ( ret_das, turn_topic )
# ret_das is a list of of DialogActs
def prepareNextDataChunk(start_data_index, reset_chunk_size_for_segment_p = False):
    global gl_agent
    print 'prepareNextDataChunk(' + str(start_data_index) + ')'

    if reset_chunk_size_for_segment_p:
        (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(start_data_index)
        possiblyAdjustChunkSize(getChunkSizeForSegment(segment_name))

    #this section of code is very similar to getDataValueListForField(data_model, segment_name), but
    #it differs in that this uses a preferred chunk size and is not limited to the chunk size
    #of the field/segment
    #choose chunk size to advance to the next segment boundary (area-code, exchange, line-number)
    min_chunk_size_to_end_of_segment = 100000
    min_segment_name = None
    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if start_data_index < segment_start_index:
            continue
        elif start_data_index > segment_end_index:
            continue
        else:
            chunk_size_to_end_of_segment = segment_end_index - start_data_index + 1
            if chunk_size_to_end_of_segment < min_chunk_size_to_end_of_segment:
                min_chunk_size_to_end_of_segment = chunk_size_to_end_of_segment
                min_segment_name = segment_name
            print 'UU in prepareNextDataChunk segment_name: ' + segment_name + ' start: ' + str(segment_start_index) + ' end: ' + str(segment_end_index) + ' consen: ' + str(start_data_index) + ' csteos: ' + str(chunk_size_to_end_of_segment)

    chunk_size_to_end_of_segment = min_chunk_size_to_end_of_segment
    segment_name = min_segment_name

    pref_chunk_size_options = gl_agent.self_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
    print 'pref_chunk_size_options: ' + str(pref_chunk_size_options)
    if pref_chunk_size_options[0][0] < chunk_size_to_end_of_segment and pref_chunk_size_options[1][0] < chunk_size_to_end_of_segment:
        print ' aa' 
        chunk_size = pref_chunk_size_options[0][0]
    #Allow a chunk that crosses segment boundaries, but only if it takes to the end of another segment
    #...but I'm taking a shortcut and not implementing that yet, just allow a larger chunk size if it's
    #the size of the phone number chunk size
    elif pref_chunk_size_options[0][0] > chunk_size_to_end_of_segment and pref_chunk_size_options[0][0] == 10:
        print ' bb'
        chunk_size = pref_chunk_size_options[0][0]
    else:
        print ' cc'
        chunk_size = chunk_size_to_end_of_segment
    
    print 'pref_chunk_size_options: ' + str(pref_chunk_size_options) + ' segment_chunk_size: ' + str(chunk_size_to_end_of_segment)
    print 'chunk_size: ' + str(chunk_size) + ' start_data_index: ' + str(start_data_index) + ' segment_name: ' + segment_name

    data_value_list = []
    total_num_digits = len(gl_agent.self_dialog_model.data_model.data_beliefs)
    last_index_to_send = start_data_index + chunk_size
    data_index_list = []
    for digit_i in range(start_data_index, min(last_index_to_send, total_num_digits)):
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
        data_index_list.append(digit_i)

    print ' data_value_list: ' + str(data_value_list)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        turn_topic = TurnTopic()
        #turn_topic.field_name = ...   omitting mention of segment_name
        turn_topic.data_index_list = data_index_list
        for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
            segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
            segment_start_index = segment_indices[0]
            segment_end_index = segment_indices[1]
            if segment_start_index == data_index_list[0] and segment_end_index == data_index_list[len(data_index_list)-1]:
                turn_topic.field_name = segment_name
        return ([digit_sequence_lf], turn_topic) 
    else:
        return (None, None)
        







#Returns a tuple ( ret_das, turn_topic )
# ret_das is a list of of DialogActs
def initiateTopicAtSegmentAndPrepareDataChunk(agent, segment_name, set_chunk_size_to_segment_chunk_size_p = True):
    print 'initiateTopicAtSegmentAndPrepareDataChunk()'

    #choose chunk size to the segment size, smaller than that, or the full phone number size
    segment_indices = agent.self_dialog_model.data_model.data_indices[segment_name]
    segment_start_index = segment_indices[0]
    segment_end_index = segment_indices[1]

    chunk_size_for_full_phone_number = getChunkSizeForSegment('telephone-number')
    chunk_size_for_segment = getChunkSizeForSegment(segment_name)

    if set_chunk_size_to_segment_chunk_size_p:
        if chunk_size_for_segment == 3 or chunk_size_for_segment == 4:
            gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
            gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
        else:
            agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInOne(chunk_size_for_segment)
            agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInOne(chunk_size_for_segment)

    pref_chunk_size_options = agent.self_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
    if pref_chunk_size_options[0][0] == chunk_size_for_full_phone_number:
        chunk_size = chunk_size_for_full_phone_number
    elif pref_chunk_size_options[0][0] < chunk_size_for_segment and pref_chunk_size_options[1][0] < chunk_size_for_segment:
        chunk_size = pref_chunk_size_options[0][0]
    else:
        chunk_size = chunk_size_for_segment

    data_value_list = []
    total_num_digits = len(agent.self_dialog_model.data_model.data_beliefs)
    last_index_to_send = segment_start_index + chunk_size
    data_index_list = []
    for digit_i in range(segment_start_index, min(last_index_to_send, total_num_digits)):
        digit_belief = agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
        data_index_list.append(digit_i)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        turn_topic = TurnTopic()
        turn_topic.field_name = segment_name
        turn_topic.data_index_list = data_index_list
        print 'returning digits ' + str(data_value_list) + ' indices: ' + str(data_index_list)
        return ([digit_sequence_lf], turn_topic) 
    else:
        return None
        


#digit_list is a list like ['six', 'five', 'zero')
#This returns a single LogicalForm, either InformTopicInfo(ItemValue(Digit or else InformTopicInfo(ItemValue(DigitSequence
def synthesizeLogicalFormForDigitOrDigitSequence(digit_list):
    if len(digit_list) == 0:
        return None
    elif len(digit_list) == 1:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(Digit(' + digit_list[0] + ')))'
    else:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(DigitSequence('
        for digit in digit_list:
            str_digit_sequence_lf += digit + ','

        #strip off the last comma
        str_digit_sequence_lf = str_digit_sequence_lf[:len(str_digit_sequence_lf)-1]
        str_digit_sequence_lf += ')))'
    
    digit_sequence_lf = rp.parseDialogActFromString(str_digit_sequence_lf)
    return digit_sequence_lf



#returns a list like ['six', 'five', 'zero'] for a field_name like 'area-code'
#segment_name == field_name
def getDataValueListForField(data_model, segment_name):
    global gl_agent

    segment_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_name)
    if segment_indices == None:
        print 'error: could not find a segment field named ' + segment_name
        return []
    segment_start_index = segment_indices[0]
    segment_end_index = segment_indices[1]
    chunk_size = segment_end_index - segment_start_index + 1
    data_value_list = []
    total_num_digits = len(gl_agent.self_dialog_model.data_model.data_beliefs)
    for digit_i in range(segment_start_index, segment_end_index+1):
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
    return data_value_list


#returns a list of integers like [0, 1, 2] which are the data indices for a field_name like 'area-code'
#segment_name == field_name
def getDataIndexListForField(data_model, segment_name):
    global gl_agent
    segment_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_name)
    if segment_indices == None:
        print 'error: could not find a segment field named ' + segment_name
        return []
    data_index_list = []
    for i in range(segment_indices[0], segment_indices[1]+1):
        data_index_list.append(i)
    return data_index_list


def getDataValuesForDataIndices(data_index_list):
    global gl_agent
    data_value_list = []
    for digit_i in data_index_list:
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
    return data_value_list










gl_10_digit_index_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

#Turn is absolute, 'self' refers to the agent.self and 'partner' refers to agent.partner.
#This is the case both for agent.self_data_model and agent.partner_data_model
#So gl_turn_mnb will be [0, 0, 1] if partner thinks it is their turn.
gl_turn_mnb = ['self', 'either', 'partner']

gl_control_mnb = ['self', 'either', 'partner']

#Degrees of handshaking aggressiveness, least = 1, most = 5
gl_handshake_level_mnb = [1, 2, 3, 4, 5]

gl_chunk_size_mnb = [1, 2, 3, 4, 10]







#retrieve data values last discussed and stored as DialogActs in gl_most_recent_data_topic_da_list
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnMostRecentTopicData(update_digit_prob):
    global gl_agent
    self_dm = gl_agent.self_dialog_model
    partner_dm = gl_agent.partner_dialog_model

    print 'updateBeliefInPartnerDataStateBasedOnMostRecentTopicData()'
    last_self_turn_topic = self_dm.getLastTurnTopic()
    turn_topic_data_index_list = last_self_turn_topic.data_index_list
    for digit_i in turn_topic_data_index_list:
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        correct_digit_value = data_value_tuple[0]
        partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, update_digit_prob)

    



#iterate update belief in partner data values for the field name passed
#This happens when the partner says they already know this field data. 
#How much do we believe them?  That is in the value of update_digit_prob passed.
def updateBeliefInPartnerDataStateForDataField(field_name, update_digit_prob):
    global gl_agent
    self_dm = gl_agent.self_dialog_model
    partner_dm = gl_agent.partner_dialog_model

    segment_indices = gl_agent.self_dialog_model.data_model.data_indices.get(field_name)
    if segment_indices == None:
        print 'error: could not find a field named ' + field_name
        return []
    segment_start_index = segment_indices[0]
    segment_end_index = segment_indices[1]
    for digit_i in range(segment_start_index, segment_end_index+1):
        digit_belief = self_dm.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        digit_value = data_value_tuple[0]
        partner_dm.data_model.setNthPhoneNumberDigit(digit_i, digit_value, update_digit_prob)




#da_list probably consists of a single DialogAct, either 
#  InformTopicInfo(ItemValue(Digit(x1)))  or else
#  InformTopicInfo(ItemValue(DigitSequence(x1, x2, x3)))  
#where x1 will be a string digit value, e.g. 'one'
#The number of digits should match the number of data indices in turn_topic.
#This walks through the digits in da_list and digit indices in turn_topic.
#The probability of this value is set to update_digit_prob, the remaining probability is set to ?,
#so update_digit_prob can be different for a check vs simple affirmation reply.
def updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(da_list, turn_topic, update_digit_prob):
    #print 'updateBeliefInPartnerDataStateBasedOnDataValuesDialogActs(da_list)'
    global gl_agent
    partner_dm = gl_agent.partner_dialog_model

    if da_list == None:
        print 'updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs() found a None da_list'
        return

    print 'da_list: ' + str(da_list)
    digit_list = collectDataValuesFromDialogActs(da_list)
    digit_index_list = turn_topic.data_index_list

    if len(digit_list) != len(digit_index_list):
        print '!!! error in updateBeliefInPartnerDataStateBasedOnDataValuesDialogActs() digit_list: ' + str(digit_list) + ' does not match len of turn_topic digit indices: ' + str(digit_index_list)
        return

    for i in range(0, len(digit_list)):
        digit_value = digit_list[i]
        digit_i = digit_index_list[i]
        partner_dm.data_model.setNthPhoneNumberDigit(digit_i, digit_value, update_digit_prob)




#This should be adjustable per requirements for correct transfer.
gl_threshold_on_belief_partner_has_wrong_value = .25





#Returns a tuple:  (list of data indices for which the confidence is high but the values disagree,
#                   list of data indices for which the recipient registers ?)
#                
def compareDataModelBeliefs():
    global gl_threshold_on_belief_partner_has_wrong_value
    digits_out_of_agreement = []
    digits_self_believes_partner_registers_unknown = []

    self_dm = gl_agent.self_dialog_model
    self_data_model_beliefs = gl_agent.self_dialog_model.data_model.data_beliefs  #a list of DigitBelief
    partner_dm = gl_agent.partner_dialog_model
    partner_data_model_beliefs = gl_agent.partner_dialog_model.data_model.data_beliefs  #a list of DigitBelief

    for i in range (0, len(self_data_model_beliefs)):
        self_digit_belief = self_data_model_beliefs[i]       #a DigitBelief
        self_belief_tup = self_digit_belief.getHighestConfidenceValue()   #a tuple e.g. ('one', .8)
        partner_digit_belief = partner_data_model_beliefs[i]
        partner_belief_tup = partner_digit_belief.getHighestConfidenceValue()   #a tuple e.g. ('one', .8)
        if self_belief_tup[0] == partner_belief_tup[0]:
            continue
        if partner_belief_tup[0] == '?':
            digits_self_believes_partner_registers_unknown.append(i)
            continue
        if partner_belief_tup[1] > gl_threshold_on_belief_partner_has_wrong_value:
            print 'compareDataModelBeliefs: ' + str(i) + ' self: ' + str(self_belief_tup) + ' partner: ' + str(partner_belief_tup)
            digits_out_of_agreement.append(i)

    print 'compareDataModelBeliefs returns digits_out_of_agreement: ' + str(digits_out_of_agreement) + ' unknown: ' + str(digits_self_believes_partner_registers_unknown)
    return (digits_out_of_agreement, digits_self_believes_partner_registers_unknown)










def dealWithMisalignedRoles():
    return gl_da_misaligned_roles

def dealWithMisalignedIndexPointer():
    return gl_da_misaligned_index_pointer

def dealWithMisalignedDigitValues(misaligned_data_value_list):
    print 'dealWithMisalignedDigitValues: ' + str(misaligned_data_value_list)
    return gl_da_misaligned_digit_values





#Dialog invitation and related banter

def generateDialogInvitation(send_or_receive):
    if send_or_receive == 'send-receive':
        return gl_da_request_dm_invitation_send_receive
    if send_or_receive == 'send':
        return gl_da_request_dm_invitation_send
    if send_or_receive == 'receive':
        return gl_da_request_dm_invitation_receive
    return []



#This is called by handleResponseToQuestion() when a "yes", "no", or "not sure" user input was detected
#that appears to be in response to a pending invitation question, "Would you like to send or receive a telephone number?"
#
# possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,
#                                            gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure,
#                                            gl_da_receive, gl_da_send)
#Returns ( ret_das, turn_topic ) or None
def handleResponseToDialogInvitationQuestion(question_da, response_da_list):
    print 'handleResponseToDialogInvitationQuestion'
    str_question_da = question_da.getPrintString()
    response_da0 = response_da_list[0]
    str_response_da0 = response_da0.getPrintString()
    print '  str_question_da:  ' + str_question_da
    print '  str_response_da0: ' + str_response_da0

    #If there's any DialogAct other than yes, no, or not sure, then disregard the yes, no, or not sure
    #DialogActs and respond based on them.
    #This is similar to handleConfirmDialogManagement_SendRole
    #In case the yes/no/not-sure DialogAct is compounded with other DialogActs on this turn,
    #strip out the yes/no/not-sure DialogActs and call generateResponseToInputDialog again recursively.
    da_list_no_ynns = []
    for da in response_da_list:
        str_da = da.getPrintString();
        if str_response_da0 != gl_str_da_correction_ti_negation and \
                str_response_da0 != gl_str_da_user_belief_no and \
                str_response_da0 != gl_str_da_user_belief_unsure and\
                str_response_da0 != gl_str_da_affirmation_yes and \
                str_response_da0 != gl_str_da_affirmation_okay and \
                str_response_da0 != gl_str_da_receive and \
                str_response_da0 != gl_str_da_send and \
                str_response_da0 != gl_str_da_user_belief_yes:
            print 'no_ynns appending ' + str_da
            da_list_no_ynns.append(da)

    print 'len(da_list_no_ynns): ' + str(len(da_list_no_ynns)) + ' len(da_list): ' + str(len(response_da_list))
    if len(da_list_no_ynns) > 0:
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_receive)
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
        return generateResponseToInputDialog(da_list_no_ynns)
    print 'hRTDIQ dropping through'

    #User declines invitation
    if str_response_da0 == gl_str_da_correction_ti_negation or \
            str_response_da0 == gl_str_da_user_belief_no or \
            str_response_da0 == gl_str_da_user_belief_unsure:
        print 'decline'
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_receive)
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
        return ([ gl_da_affirmation_okay, gl_da_standing_by ], None)

    #User accepts invitation
    if str_response_da0 == gl_str_da_affirmation_yes or \
            str_response_da0 == gl_str_da_affirmation_okay or \
            str_response_da0 == gl_str_da_user_belief_yes:
        print 'accept'

        #If the user not only gives an affirmation but makes a request, then clear the question and process the request.
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_receive)

        #If invitation was send_receive, tell tell partner that self is not able to receive a phone number yet,
        #would they like to receive a phone number?
        if str_question_da == gl_str_da_request_dm_invitation_send_receive:
            possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,\
                                                       gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure,\
                                                       gl_da_receive, gl_da_send)
            removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
            pushQuestionToPendingQuestionList(gl_turn_number, 'self', gl_da_request_dm_invitation_receive, 
                                              gl_str_da_request_dm_invitation_receive, (possible_answers_to_invitation_question))
            ret_das = [ gl_da_inform_dm_self_correction, gl_da_inform_dm_self_not_able_receive, gl_da_inform_dm_self_able_send,\
                        gl_da_request_dm_invitation_receive ]
            return (ret_das, None)        #XX need to fill in the turn_topic

        #If invitation was receive, start the process
        if str_question_da == gl_str_da_request_dm_invitation_receive:
            print 'partner accepted invitation to receive a phone number'

            removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_receive)

            gl_agent.setRole('send', gl_default_phone_number)
            initializeStatesToSendPhoneNumberData(gl_agent)
            
            str_da_say_phone_number_is = gl_str_da_say_field_is.replace('$30', 'telephone-number')
            da_say_phone_number_is = rp.parseDialogActFromString(str_da_say_phone_number_is)

            ret_das = [ gl_da_affirmation_okay, da_say_phone_number_is ]
            #here we need to make sure the area code is introduced, but this should happen within
            #prepareNextDataChunk noticing the handshake/topic-continuation context
            (data_chunk_das, turn_topic) = prepareNextDataChunk(0)
            ret_das.extend(data_chunk_das)
            return (ret_das, turn_topic)

    #If invitation was to send or receive and the user is explicit about receiving, then do that
    if str_response_da0 == gl_str_da_receive:
        print 'receive'            
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_receive)
        gl_agent.setRole('send', gl_default_phone_number)
        initializeStatesToSendPhoneNumberData(gl_agent)
        str_da_say_phone_number_is = gl_str_da_say_field_is.replace('$30', 'telephone-number')
        da_say_phone_number_is = rp.parseDialogActFromString(str_da_say_phone_number_is)
        ret_das = [ gl_da_affirmation_okay, da_say_phone_number_is ]
        (data_chunk_das, turn_topic) = prepareNextDataChunk(0)
        ret_das.extend(data_chunk_das)
        return (ret_das, turn_topic)


    #If invitation was to send or receive and the user is explicit about sending, then do that
    if str_response_da0 == gl_str_da_send:
        print 'send'
        possible_answers_to_invitation_question = (gl_da_correction_ti_negation, gl_da_affirmation_yes, gl_da_affirmation_okay,\
                                                   gl_da_user_belief_yes, gl_da_user_belief_no, gl_da_user_belief_unsure,\
                                                   gl_da_receive, gl_da_send)
        removeQuestionFromPendingQuestionList('self', gl_da_request_dm_invitation_send_receive)
        pushQuestionToPendingQuestionList(gl_turn_number, 'self', gl_da_request_dm_invitation_receive, 
                                          gl_str_da_request_dm_invitation_receive, (possible_answers_to_invitation_question))
        ret_das = [ gl_da_inform_dm_self_correction, gl_da_inform_dm_self_not_able_receive, gl_da_inform_dm_self_able_send,\
                    gl_da_request_dm_invitation_receive ]
        return (ret_das, None)

    ret_das = [ gl_da_i_heard_you_say ]
    ret_das.extend(response_da_list)
    ret_das.append(gl_da_misalignment_self_hearing_or_understanding)
    return ( ret_das, None )      #XX need to fill in the turn_topic


    
        

def testDataAgreement(agent):
    return None
    


#10 time ticks per second
gl_time_tick_ms = 100

#how much to adjust turn confidence toward self, per time tick
#10 time ticks per second * .01 = 10 seconds to move turn all the way to self
#gl_time_tick_turn_delta = .01 
gl_time_tick_turn_delta = .02


#If self's turn confidence gets to this value after waiting for partner's response,
#then take the initiative and say something.
#This is very crude, because the propensity to say something should depend on whether
#self has something to say or not.
gl_wait_turn_conf_threshold = .6



### NOTE: This is called in a different thread from the main thread.
#
def handleTimingTick():
    global gl_agent
    global gl_use_speech_p
    global gl_speech_recognizer
    global gl_currently_performing_audio_output_p
    if gl_agent == None:
        return

    #if partner is speaking then return the turn to them
    if gl_use_speech_p:        
        # phase0 is not listening, but could be processing
        # phase1 is listening for speech to start
        # phase2 is listening for speech to stop
        speech_phase = gl_speech_recognizer.getListenState()
        #print 'speech_phase: ' + speech_phase
        if speech_phase == 'phase2' or speech_phase == 'phase0':
            resetCurrentTurnBeliefs()

    #If self is currently speaking or otherwise performing audio output, then reset turn beleifs to self.
    if gl_currently_performing_audio_output_p:
        resetCurrentTurnBeliefs()
        return 

    gl_agent.adjustTurnTowardSelf(gl_time_tick_turn_delta)
    val = int(gl_agent.self_dialog_model.getTurnConfidence('self') * 10)
    #print 'val: ' + str(val)
    #if (gl_agent.self_dialog_model.getTurnConfidence('self') * 100) % 100 == 0:
    #    print 'self turn confidence: ' + str(gl_agent.self_dialog_model.getTurnConfidence('self'))

    if gl_agent.self_dialog_model.getTurnConfidence('self') > gl_wait_turn_conf_threshold:
        #print 'handleTimingTick sees self turn confidence ' + str(gl_agent.self_dialog_model.getTurnConfidence('self')) + ' calling IssueOutputAfterWaitTimeout()'
        issueOutputAfterWaitTimeout()



#This gets triggered after self's turn confidence exceeds a threshold after waiting for partner to
#execute their turn.
#This will be called on a different thread from the main thread, so beware simultaneous
#access of the data values.
def issueOutputAfterWaitTimeout():
    global gl_dialog_act_queue

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
    if last_self_utterance_tup == None:
        return
    da_list = last_self_utterance_tup[2]
    last_self_utterance_contains_inform_digits_p = False
    for da in da_list:
        str_da = da.getPrintString()
        if str_da.find('InformTopicInfo(ItemValue(Digit') == 0:
            last_self_utterance_contains_inform_digits_p = True


    #print 'last_self_utterance_contains_inform_digits_p: ' + str(last_self_utterance_contains_inform_digits_p)
    output_da_list = None
    synthesized_confirm_da_list = [gl_da_affirmation_okay]
    if last_self_utterance_contains_inform_digits_p == True:
        gl_dialog_act_queue.append(('Timeout', synthesized_confirm_da_list))
        
        




gl_wait_timer = None


class WaitTimer():
    def __init__(self, interval_msec, callout_function):
        self.running_p = True
        self.timer_thread_id = thread.start_new_thread(self.timer_thread_function, (interval_msec, callout_function))

    def timer_thread_function(self, interval_msec, callout_function):
        interval_sec = interval_msec/1000.0
        while self.running_p:
            #print 'tick'
            callout_function()
            time.sleep(interval_sec)

    def stopTimer(self):
        self.running_p = False
        print ' timer should now be stopped'


def createAndStartWaitTimer(interval_msec):
    global gl_wait_timer
    if gl_wait_timer == None:
        gl_wait_timer = WaitTimer(interval_msec, handleTimingTick)

def stopTimer():
    global gl_wait_timer
    if gl_wait_timer == None:
        print 'no timer to stop'
        return
    gl_wait_timer.stopTimer()
    gl_wait_timer = None




#
#
###############################################################################


###############################################################################
#
#ASR and TTS
#


######################################
#
#ASR Automatic Speech Recognition
#
#Using the SpeechRecognition package
#https://pypi.python.org/pypi/SpeechRecognition/
#

#This borrows from 
#Python/Lib/site-packages/speech_recognition/__main__

gl_speech_recognizer = None
gl_microphone = None


#gl_energy_threshold = 100
gl_energy_threshold = 200

def setSpeechEnergyThreshold(val):
    gl_energy_threshold = val


#The speech_recognizer sample demo uses dynamic adjustment of mic energy threshold.
#I found this not to work very well, so we pass in an energy threshold
def initializeASR(energy_threshold):
    global gl_speech_recognizer
    global gl_microphone
    global gl_energy_threshold

    gl_speech_recognizer = sr.Recognizer()
    gl_microphone = sr.Microphone()

    #The speech_recognizer sample demo uses dynamic adjustment of mic energy threshold.
    #I found this not to work very well.
    print("Calibrating background mic energy, a moment of silence please for this")
    with gl_microphone as source: gl_speech_recognizer.adjust_for_ambient_noise(source)
    print("possibly recommending an energy_threshold of {}".format(gl_speech_recognizer.energy_threshold))

    gl_speech_recognizer.dynamic_energy_threshold = False
    gl_speech_recognizer.energy_threshold = gl_energy_threshold
    gl_speech_recognizer.pause_threshold = .3
    gl_speech_recognizer.non_speaking_duration = min(gl_speech_recognizer.non_speaking_duration,\
                                                         gl_speech_recognizer.pause_threshold)
    print("Recognizer pause_threhsold is now " + str(gl_speech_recognizer.pause_threshold))




#When speech is detected and recognized, callback_function is called with the recognized text 
#string is sent as the function argument.
class SpeechRunner():
    def __init__(self, callback_function):
        self.stop_p = False
        self.speechrunner_thread_id = thread.start_new_thread(self.speech_runner_thread_function, (callback_function,))

    def speech_runner_thread_function(self, callback_function):
        global gl_microphone
        global gl_speech_recognizer
        global gl_speech_runner_running_p
        global gl_speech_runner

        print 'Entering speech_runner_thread_function'

        while True and gl_speech_runner != None:
            print("Say something!")
            #this will block while it waits for input
            #http://stackoverflow.com/questions/11195140/python-break-or-exit-out-of-with-statement
            with gl_microphone as source: audio = gl_speech_recognizer.listen(source)

            #In case this SpeechRecognizer has been terminated while listening


            #if self.running_p == False:
            #    print 'got audio but this SpeechRecognizer is terminated'
            #    return

            print("Got it! Now to recognize it...")
            try:
                if self.stop_p:
                    print 'Quitting out of speech_runner_thread_function'
                    gl_speech_runner = None
                    return

                if audio == None:
                    print 'audio is None but we didnt quit out?'
                    gl_speech_runner = None
                    return

                # recognize speech using Google Speech Recognition
                value = gl_speech_recognizer.recognize_google(audio)



                # we need some special handling here to correctly print unicode characters to standard output
                if str is bytes: # this version of Python uses bytes for strings (Python 2)
                    the_text = u"{}".format(value).encode("utf-8")
                    #print(u"You said {}".format(value).encode("utf-8"))
                else: # this version of Python uses unicode for strings (Python 3+)
                    the_text = "{}".format(value)
                    #print("You said {}".format(value))
                print 'You said ' + the_text
                the_text = spellOutDigits(the_text)

                #The speech might have been picked up while pause was set
                #if gl_speech_runner_paused_p == True:
                #    print 'something was recognized while we speech recognition was supposed to be paused: '
                #    print 'the_text: ' + the_text
                #else:
                #    print 'the_text: ' + the_text
                #    callback_function(the_text)
                callback_function(the_text)

            except sr.UnknownValueError:
                print("Oops! Didn't catch that")
            except sr.RequestError as e:
                print("Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))

        print 'Exiting speech_runner_thread_function'
        gl_speech_runner = None
    
    def stop(self):
        global gl_speech_recognizer
        self.stop_p = True
        gl_speech_recognizer.stopListening()
        print ' speech_runner stop issued'

#    def start(self):
#        self.running_p = True
#        print ' speech_runner should now be started'


gl_speech_runner = None

def startNewSpeechRecRunner():
    print 'startNewSpeechRecRunner'
    global gl_speech_runner
    if gl_speech_runner != None:
        print '  calling gl_speech_runner.stop()'
        gl_speech_runner.stop()
    count = 0
    while gl_speech_runner != None:
        count += 1
        if count > 10000:
            print 'timeout waiting for gl_speech_runner_to_stop'
            break
        time.sleep(.005)
    print 'startNewSpeechRecRunner timeout count: ' + str(count)
    if gl_speech_runner != None:
        print 'could not start a new speech runner because the old one has not stopped'
        return
    gl_speech_runner = SpeechRunner(handleSpeechInput)


#def startNewSpeechRecRunner():
#    global gl_speech_runner
#    if gl_speech_runner == None:
#        gl_speech_runner = SpeechRunner(handleSpeechInput)
#    gl_speech_runner.start()


def stopSpeechRunner():
    global gl_speech_runner
    if gl_speech_runner == None:
        print 'no speech_runner to stop'
        return
    gl_speech_runner.stop()



#def pauseSpeechRunner():
#    global gl_speech_runner
#    global gl_speech_runner_paused_p
#    if gl_speech_runner == None:
#        print 'no speech_runner to pause'
#        return
#    gl_speech_runner.stop()
#    gl_speech_runner_paused_p = True


#def resumeSpeechRunner():
#    global gl_speech_runner
#    global gl_speech_runner_paused_p
#    if gl_speech_runner == None:
#        print 'no speech_runner to resume'
#        return
#    gl_speech_runner.start()
#    gl_speech_runner_paused_p = False




#ASR normally returns numerals for digits, we spell them out.
#An isolated "two" is sometimes recognized as 'too'.
#And what else...?
def spellOutDigits(text_string):
    #print 'spell out digits input: ' + text_string
    text_string = text_string.replace('0', ' zero ')
    text_string = text_string.replace('to one', ' two one') #'one to one'
    text_string = text_string.replace('1', ' one ')
    text_string = text_string.replace('2', ' two ')
    text_string = text_string.replace('too', ' two ')
    text_string = text_string.replace('3', ' three ')
    text_string = text_string.replace('4', ' four ')
    text_string = text_string.replace('5', ' five ')
    text_string = text_string.replace('6', ' six ')
    text_string = text_string.replace('sex', ' six ')
    text_string = text_string.replace('7', ' seven ')
    text_string = text_string.replace('8', ' eight ')
    text_string = text_string.replace('9', ' nine ')
    text_string = text_string.replace('wright', ' right ')
    text_string = text_string.replace('Wright', ' right ')
    #print 'spell out digits output: ' + text_string
    return text_string



gl_indexical_relative_map = {'first':0, 'second':1, 'third':2, 'fourth':3, 'fifth':4,\
                             'sixth':5, 'seventh':6, 'eighth':7, 'ninth':8, 'tenth':9,\
                             'eleventh':10, 'twelvth':11}


#returns the index relative to the entire telephone number for the target_digit_ith relative to field_name
#In other words, if you say, what is the first digit of the exchange, this returns 3
def getDigitIndexForFieldRelativeIndex(field_name, target_digit_ith):
    print 'getDigitIndexForFieldRelativeIndex(' + field_name + ' ' + str(target_digit_ith) + ')'
    segment_indices = gl_agent.self_dialog_model.data_model.data_indices[field_name]
    segment_start_index = segment_indices[0]
    return segment_start_index + target_digit_ith




#
#
######################################

######################################
#
#TTS Text to Speech
#
#Using the gTTS package 
#https://pypi.python.org/pypi/gTTS
#


#A flag that is True when text-to-speech audio output is ongoing.
gl_currently_performing_audio_output_p = False


def ttsSpeakText(tts_string):
    global gl_tts_temp_file
    global gl_currently_performing_audio_output_p

    tts = gTTS(text=tts_string, lang='en')
    tts.save(gl_tts_temp_file)

    stopSpeechRunner()

    gl_currently_performing_audio_output_p = True
    print 'playMP3 start'
    playMP3(gl_tts_temp_file)
    print 'playMP3 done'
    gl_currently_performing_audio_output_p = False
    #start listening again
    startNewSpeechRecRunner()






#This is to play an mp3 file.
#It only works on Windows.  We'll have to figure out something else
#for other platforms.
#
#https://lawlessguy.wordpress.com/2016/02/10/play-mp3-files-with-python-windows/
# Copyright (c) 2011 by James K. Lawless
# jimbo@radiks.net http://www.mailsend-online.com
# License: MIT / X11
# See: http://www.mailsend-online.com/license.php
# for full license details.
 
from ctypes import *;

gl_platform = platform.platform()

if gl_platform.find('Windows') == 0:

    winmm = windll.winmm
 
    def mciSend(s):
        i=winmm.mciSendStringA(s,0,0,0)
        if i<>0:
            print "Error %d in mciSendString %s" % ( i, s )
 
    def playMP3(mp3Name):
        mciSend("Close All")
        mciSend("Open \"%s\" Type MPEGVideo Alias theMP3" % mp3Name)
        mciSend("Play theMP3 Wait")
        mciSend("Close theMP3")


if gl_platform.find('Darwin') == 0:

    #http://stackoverflow.com/questions/3498313/how-to-trigger-from-python-playing-of-a-wav-or-mp3-audio-file-on-a-mac
    import subprocess
    def playMP3(mp3Name):
        subprocess.call(["afplay", mp3Name])





   

#But guess what, google tts apparenly only outputs an mp3 file, not a wav file.
#http://stackoverflow.com/questions/6951046/pyaudio-help-play-a-file
def playWavFile(wav_filepath):

    # length of data to read.
    play_chunk_size = 1024
    

    # open the file for reading.
    wf = wave.open(wav_filepath, 'rb')

    # create an audio object
    p = pyaudio.PyAudio()

    # open stream based on the wave object which has been input.
    stream = p.open(format =
                    p.get_format_from_width(wf.getsampwidth()),
                    channels = wf.getnchannels(),
                    rate = wf.getframerate(),
                    output = True)

    # read data (based on the play_chunk_size)
    data = wf.readframes(play_chunk_size)

    # play stream (looping from beginning of file to the end)
    while data != '':
        # writing to the stream is what *actually* plays the sound.
        stream.write(data)
        data = wf.readframes(play_chunk_size)

    # cleanup stuff.
    stream.close()    
    p.terminate()


#
#
######################################
#
###############################################################################



###############################################################################
#
#Utils
#

#I'm pretty sure there's a shorter way to do this using some pythonic magic like map or something
def extractItemsFromCommaSeparatedListString(str_comma_sep_items):
    str_item_list = []
    #print 'extractItemsFromCommaSeparatedListString(' + str_comma_sep_items + ')'
    
    l1 = str_comma_sep_items.split(',')
    #print 'extractItems...l1: ' + str(l1)
    for item in l1:
        item = item.strip()
        #print ' item: ' + item
        str_item_list.append(item)
    return str_item_list
    


gl_transcript_filename = 'da-transcript.text'
gl_transcript_filepath = os.path.join(gl_home, gl_transcript_filename)
gl_transcript_file = None


def setTranscriptFilepath():
    global gl_transcript_filename
    global gl_transcript_filepath
    username = getpass.getuser()
    str_date = time.strftime('%Y_%m_%d')
    gl_transcript_filename = 'da-transcript_' + username + '_' + str_date + '.text'
    gl_transcript_filepath = os.path.join(gl_home, gl_transcript_filename)
    print 'gl_transcript_filepath: ' + gl_transcript_filepath


def openTranscriptFile():
    global gl_transcript_filepath
    global gl_transcript_file
    gl_transcript_file = open(gl_transcript_filepath, 'a+')
    str_date = time.strftime('%Y/%m/%d')
    str_time = time.strftime('%H:%m:%d')
    gl_transcript_file.write('\n' + str_date + ' ' + str_time + '\n')

def writeToTranscriptFile(text_string):
    global gl_transcript_file
    if gl_transcript_file.closed:
        print 'gl_transcript_file is closed'
        return
    gl_transcript_file.write(text_string + '\n')

def closeTranscriptFile():
    global gl_transcript_file
    gl_transcript_file.close()
    



                        

#
#
###############################################################################



###############################################################################
#
#archives
#





# XX This needs to be re-written
#1. Determine whether the next chunk of data is a topic continuation with the last topic info.
#   If not, then the data index should be included, i.e. the segment name, or digit index.
#   This will have something to do with the data_index_pointer.
#   If data_index_pointer is 0, then introduce the first segment.
#2. Determine if the handshaking level requires that data index be included.
#
# 


#Compares self and partner data_model beliefs, and prepares a next set of DialogActs to send.
#Under a normal send situation, the delta in data_model beliefs will be the partner holding unknown (?)
#data values for the next segment, as indicated by the consensus index pointer.
#If this is the case, then just the data of the next segment are queued up as DialogActs.
#If however partner's data_model has a high confidence conflict with self's, or if the 
#first unknown digit is not the start of the next consensus index pointer segment, then
#this prepares a sequence of DialogActs that calls out the segment name explicitly.
def prepareNextDataChunkBasedOnDataBeliefComparisonAndIndexPointersOld(force_declare_segment_name=False):
    global gl_agent
    (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

    print 'prepareNextDataChunkBasedOn... force_declare: ' + str(force_declare_segment_name)
    
    consensus_index_pointer = gl_agent.getConsensusIndexPointer()
    print 'consensus_index_pointer: ' + str(consensus_index_pointer)
    data_index_of_focus = None

    #Assume the unknown digits are in small-to-large order.
    if len(self_belief_partner_is_wrong_digit_indices) > 0:
        data_index_of_focus = self_belief_partner_is_wrong_digit_indices[0]

    #Assume the unknown digits are in small-to-large order.
    if len(self_belief_partner_registers_unknown_digit_indices) > 0:
        data_index_of_focus = self_belief_partner_registers_unknown_digit_indices[0]

    #we're done actually
    if data_index_of_focus == None:
        gl_agent.setRole('banter')
        return ([gl_da_all_done], None)   #XX need to fill in the turn_topic

    print 'data_index_of_focus: ' + str(data_index_of_focus)

    #Most of the time, this will just hit on the next chunk of digits to send.
    if consensus_index_pointer != None and \
       consensus_index_pointer == data_index_of_focus and \
       not force_declare_segment_name and\
       consensus_index_pointer != 0:
        return prepareNextDataChunkOld(gl_agent)

    # Need to do more here to catch mismatch

    #If we drop through to here, then say explicitly what chunk segment we're delivering next
    (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(data_index_of_focus)
    print 'dropping through ee, data_index_of_focus: ' + str(data_index_of_focus) + ' segment_name: ' + segment_name + ' chunk_size: ' + str(chunk_size)

    return handleSendSegmentChunkNameAndData(segment_name)

    #This is broken. Do not say the segment_name and then call prepareNextDataChunk because the data chunk size might
    #not be the size of the segment.
    #gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    #gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    #str_da_say_item_type = gl_str_da_say_item_type.replace('$1', segment_name)
    #da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
    #ret = [da_say_item_type]
    #ret.extend(prepareNextDataChunk(gl_agent))
    #return ret



#Returns a tuple ( ret_das, turn_topic )
# ret_das is a list of of DialogActs
def prepareNextDataChunkOld(agent):
    print 'prepareNextDataChunkOld'
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        print 'prepareNextDataChunkOld encountered misaligned consensus_index_pointer, calling again with tell=True'
        agent.getConsensusIndexPointer(True)
        return ([dealWithMisalignedIndexPointer()], None)  #XX need to fill in the turn_topic

    if consensus_index_pointer >= 10:
        return ([gl_da_all_done], None)    #XX need to fill in the turn_topic


    #this section of code is very similar to getDataValueListForField(data_model, segment_name), but
    #it differs in that this uses a preferred chunk size and is not limited to the chunk size
    #of the field/segment
    #choose chunk size to advance to the next segment boundary (area-code, exchange, line-number)
    min_chunk_size_to_end_of_segment = 100000
    min_segment_name = None
    for segment_name in agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if consensus_index_pointer < segment_start_index:
            continue
        elif consensus_index_pointer > segment_end_index:
            continue
        else:
            chunk_size_to_end_of_segment = segment_end_index - consensus_index_pointer + 1
            if chunk_size_to_end_of_segment < min_chunk_size_to_end_of_segment:
                min_chunk_size_to_end_of_segment = chunk_size_to_end_of_segment
                min_segment_name = segment_name
            print 'UU in prepareNextDataChunk segment_name: ' + segment_name + ' start: ' + str(segment_start_index) + ' end: ' + str(segment_end_index) + ' consen: ' + str(consensus_index_pointer) + ' csteos: ' + str(chunk_size_to_end_of_segment)

    chunk_size_to_end_of_segment = min_chunk_size_to_end_of_segment
    segment_name = min_segment_name

    pref_chunk_size_options = agent.self_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
    print 'pref_chunk_size_options: ' + str(pref_chunk_size_options)
    if pref_chunk_size_options[0][0] < chunk_size_to_end_of_segment and pref_chunk_size_options[1][0] < chunk_size_to_end_of_segment:
        print ' aa' 
        chunk_size = pref_chunk_size_options[0][0]
    #Allow a chunk that crosses segment boundaries, but only if it takes to the end of another segment
    #...but I'm taking a shortcut and not implementing that yet, just allow a larger chunk size if it's
    #the size of the phone number chunk size
    elif pref_chunk_size_options[0][0] > chunk_size_to_end_of_segment and pref_chunk_size_options[0][0] == 10:
        print ' bb'
        chunk_size = pref_chunk_size_options[0][0]
    else:
        print ' cc'
        chunk_size = chunk_size_to_end_of_segment
    
    print 'pref_chunk_size_options: ' + str(pref_chunk_size_options) + ' segment_chunk_size: ' + str(chunk_size_to_end_of_segment)
    print 'chunk_size: ' + str(chunk_size) + ' consensus_index_pointer: ' + str(consensus_index_pointer) + ' segment_name: ' + segment_name

    data_value_list = []
    total_num_digits = len(agent.self_dialog_model.data_model.data_beliefs)
    last_index_to_send = consensus_index_pointer + chunk_size
    data_index_list = []
    for digit_i in range(consensus_index_pointer, min(last_index_to_send, total_num_digits)):
        digit_belief = agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
        data_index_list.append(digit_i)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        turn_topic = TurnTopic()
        #turn_topic.field_name = ...   omitting mention of segment_name
        turn_topic.data_index_list = data_index_list
        return ([digit_sequence_lf], turn_topic) 
    else:
        return None
        



#This was lifted from handleInformTopicData_Send in order to use it also
#in RequestTopicInfo(request-confirmation)
#The partner is providing a list of DialogActs that include information about digit data.
#(The DialogActs are strung together from a single utterance.)
#The DialogActs might also include indicators of confusion, such as what?
#These DialogActs need to be compared with correct digit data, partly though alignment search.
#This returns a tuple: 
# (partner_expresses_confusion_p, match_count, check_match_segment_name, partner_digit_word_sequence)
#
def comparePartnerReportedDataAgainstSelfDataOld(da_list):
    print 'comparePartnerReportedDataAgainstSelfDataOld(da_list)'
    for da in da_list:
        print '    ' + da.getPrintString()

    partner_digit_word_sequence = []
    partner_expresses_confusion_p = False

    #could be an interspersing of ItemValue(Digit( and ItemValue(DigitSequence
    for da in da_list:
        str_da = da.getPrintString()
        print str_da
        d_index = str_da.find('ItemValue(Digit(')
        ds_index = str_da.find('ItemValue(DigitSequence(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = str_da.find(')', start_index)
            partner_check_digit_value = str_da[start_index:rp_index]
            partner_digit_word_sequence.append(partner_check_digit_value)

        elif ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = str_da.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(str_da[start_index:rp_index])
            partner_digit_word_sequence.extend(digit_value_list)

        #temporarily uncommenting XX
        #Commenting this out because it inserts '?' for things like "what is six five zero" 
        #This applies to an isolated 'what?' or other non-digit which we intend to have substituted for a digit value so
        #is indicative of confusion
        #But the danger is that 'what' said with other words will be interpreted as confusion when it is not,
        #and the system speaks 'I'll repeat that' when they really shouldn't.
        elif str_da not in gl_digit_list and str_da.find('RequestDialogManagement(what)') == 0:
            #partner indicates confusion so we surmise they have not advanced their index pointer with this data chunk.
            #So reset the tentative_partner_index_pointer.
            partner_expresses_confusion_p = True
            #Add ? partner utterance explicitly into the list of digits we heard them say, in order to
            #pinpoint the index pointer for their indicated check-confusion
            partner_digit_word_sequence.append('?')


    #This is a problem because it allows a match to a self utterance like, "I heard you say six five zero I did not understand that"
    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    last_self_utterance_da_list = last_self_utterance_tup[2]

    #Commenting this out because it does not allow "what is six five zero" after self has said that it does not understand something else.
    #for da in last_self_utterance_da_list:
    #    if da.getPrintString().find(gl_str_da_misalignment_any) >= 0:
    #        print 'comparePartnerReportedDataAgainstSelfData sees that the last self utterance had a misalignment ' 
    #        print '   ' + da.getPrintString()
    #        print ' (False, 0, None, [])'
    #        return (False, 0, None, [])
    
    last_sent_digit_value_list = collectDataValuesFromDialogActs(last_self_utterance_da_list)
    # last self utterances that don't convey information
    self_data_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()

    print 'last_sent_digit_value_list: ' + str(last_sent_digit_value_list) + ' partner_digit_word_sequence: ' + str(partner_digit_word_sequence)

    #Here try to align partner's check digit sequence with what self has just provided as a partial digit sequence,
    #or else with the context of previously provided values, or even with correct data that has not been provided
    #in this conversation (i.e. if partner knows the phone number already)
    
    #This returns match_count = 0 if the partner_digit_word_sequence contains any errors or an 
    #alignment match to self's data model cannot be found.
    check_match_tup = registerCheckDataWithLastSaidDataAndDataModelOld(partner_digit_word_sequence, last_sent_digit_value_list, self_data_index_pointer)

    match_count = check_match_tup[0]
    #print 'match_count: ' + str(match_count)
    #print 'check_match_tup: ' + str(check_match_tup)
    check_match_segment_name = check_match_tup[1]

    print 'CComparePartner returning: ' + str((partner_expresses_confusion_p, match_count, check_match_segment_name, partner_digit_word_sequence))
    
    return (partner_expresses_confusion_p, match_count, check_match_segment_name, partner_digit_word_sequence)



####
#This is obsolete because it is too simplistic.
#This advances the index pointer belief of the agent's self and partner data models by chunk_size
#Instead, we only advance the belief in the partner index pointer when we believe they have received the data
#and it is correct.  The partner may have advanced their data index pointer, but if self believes they have
#gotten the information incorrect, then self may have to correct them.
#Only then do we advance the self index pointer.
#
def advanceIndexPointerBeliefsOld(agent):
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        return [dealWithMisalignedIndexPointer()]

    if consensus_index_pointer >= 10:
        return [gl_da_all_done];

    chunk_size = agent.self_dialog_model.protocol_chunk_size.getDominantValue()

    next_data_index_pointer_loc = consensus_index_pointer + chunk_size

    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)
    agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)

    print 'adancing index pointer by chunk_size: ' + str(chunk_size) + ' to ' + str(consensus_index_pointer)
#
#####




#return 'middle' or 'at-end'
def advanceSelfIndexPointerOld(agent, pointer_advance_count):
    self_dm = agent.self_dialog_model
    self_index_pointer = self_dm.data_index_pointer.getDominantValue()

    #if self_index_pointer >= 9:
    #    return 'done-already'
    
    next_data_index_pointer_loc = self_index_pointer + pointer_advance_count
    if next_data_index_pointer_loc >= len(gl_10_digit_index_list):
        agent.self_dialog_model.data_index_pointer.setEquallyDistributed()
        return 'at-end'
        
    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)
    print 'advancing self index pointer by : ' + str(pointer_advance_count) + ' to ' + str(next_data_index_pointer_loc)
    return 'middle'




#partner_digit_word_sequence is a sequence of data value words sent as check data by partner. These could include '?'
#last_sent_digit_value_list is a sequence of data value words most recently sent by self.
#This attempts to register the partner_digit_word_sequence with last_sent_digit_value_list, and also with 
#the digit sequence in gl_agent.self_dialog_model.data_model.
#Examples: 
#       sent   six five zero
#      check   six five zero
#
#       sent   six five zero
#      check   six five
#
#       sent   six five zero
#      check   six 
#
#       sent   six five zero
#      check       five zero
#
#       sent   six five zero
#      check       five
#
#       sent   six five zero
#      check            zero
#
#       sent   six five zero
#      check   six      zero
#
#       sent   six five zero
#      check   eight
#
#       sent   six five zero
#      check       four zero
#
#      model   six five zero  six three nine one two one two
#       sent   six five zero
#      check   six five zero  six three nine
#
#      model   six five zero  six three nine one two one two
#       sent   six five zero
#      check                  six three nine
#
#       sent   three three two
#      check   three
#
#       sent   three three two
#      check   three three
#
#       sent   three three two
#      check         three two
#
#       sent   three three two
#      check   three seven
#
#       sent   three three two
#      check   three two   two
#
#       sent   three two three
#      check   three 
#
#       sent   three three three
#      check   three three
#
#       sent   three three three
#      check   three 
#
#       sent   eight two seven
#      check   four  two
#
#       sent   eight two seven
#      check         two six
#
#       sent   eight two seven
#      check   nine  one
#
#       sent   eight two seven
#      check   eight ?
#
#       sent   eight two seven
#      check   eight ?   seven
#
#       sent   eight two seven
#      check             seven ?
#
#       sent   eight two seven
#      check   nine 
#
#      model   six five zero  nine three nine one two one two
#       sent   six five zero
#      check   nine
#
#      model   six five zero  nine three nine one two one two
#       sent   six five zero
#      check   nine three
#
#
#previously: 
#       sent   six five
#      check   six five
#this turn:
#       sent            zero
#      check            zero
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check   six five zero
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check       five zero
#
#       sent            zero
#      check       five eight
#
#       sent            zero
#      check            eight
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check       four zero
#   
#Cases:
#-If len(partner_check_digit_sequence) <= len(last_said_digit_list), then
# register first digit to first digit.
# -If all digits match, then return the number of matching digits
# -If any digits don't match, then return 0 for the number of successful matches.
#
#-If len(partner_check_digit_sequence) > len(last_said_digit_list), then
# register last digit to last digit.
# If all digits match, then check the remaining preceeding digits of partner_check_digit_sequence
# with the correct data model.  If these all match, then return len(last_said_digit_list) to
# to show that all digits just said were gotten correctly and put correctly in context.
#
#(This not implemented yet:
#-If num matching return is 0, then finally check to see if the partner_check_digits match
# the following data values.  If so, then in the second position of the tuple return the
# name of the next segment.)
#
#Normally, self_data_index_pointer will point a the first last_said_digit
#
#Returns a tuple (num_digits_matched, name_of_next_segment_if_fully_matched)
#If a full match of partner_check_digit_sequence is not achieved, then this returns 
#(0, None).   
#This is still lacking in that it does not detect a match to data not included in the last_said_digit_list.
#
def registerCheckDataWithLastSaidDataAndDataModelOld(partner_check_digit_sequence, last_said_digit_list, self_data_index_pointer):
    global gl_agent

    print 'registerCheck... partner: ' + str(partner_check_digit_sequence) + ' last_said: ' + str(last_said_digit_list) + ' self_data_index_pointer: ' + str(self_data_index_pointer)
    match_p = True
    if len(partner_check_digit_sequence) <= len(last_said_digit_list):
        i = 0
        while i < len(partner_check_digit_sequence):
            if partner_check_digit_sequence[i] != last_said_digit_list[i]:
                match_p = False
                break
            i += 1
        if match_p == True:
            return (i, None)

    elif len(partner_check_digit_sequence) > len(last_said_digit_list):
        i_last_said = len(last_said_digit_list)-1
        i_partner =  len(partner_check_digit_sequence)-1
        while i_last_said >= 0:
            print 'a1: i_last_said: ' + str(i_last_said) + ' i_partner: ' + str(i_partner)
            if partner_check_digit_sequence[i_partner] != last_said_digit_list[i_last_said]:
                print 'mismatch: ' + partner_check_digit_sequence[i_partner] + ' != ' + last_said_digit_list[i_last_said]
                match_p = False
                break
            i_partner -= 1
            i_last_said -= 1
        if i_partner > self_data_index_pointer:
            print 'b1 i_partner: ' + str(i_partner) + ' > self_data_index_pointer: ' + str(self_data_index_pointer)
            match_p = False

        sdip = self_data_index_pointer-1
        print ' i_partner: ' + str(i_partner) + ' i_last_said: ' + str(i_last_said) + ' sdip: ' + str(sdip)
        if match_p == True:
            while i_partner >= 0:
                self_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[sdip]
                self_data_value_tuple = self_digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
                self_data_value = self_data_value_tuple[0]
                if partner_check_digit_sequence[i_partner] != self_data_value:
                    print ' c1 partner_check_digit_sequence[i_partner]: ' + partner_check_digit_sequence[i_partner] + ' != self_data_value: ' + self_data_value
                    match_p = False
                    break
                i_partner -= 1
                sdip -= 1
        if match_p == True:
            return (len(last_said_digit_list), None)

    #drop through to here if a match failure, check to see if the partner_check_digit_sequence matches another segment
    #This not written yet
    print 'dd drop through'

    actual_segment_names = findSegmentNameForDigitList(partner_check_digit_sequence)
    print 'actual_segment_names: ' + str(actual_segment_names)
    if actual_segment_names != None and len(actual_segment_names) == 1:
        actual_segment_name = actual_segment_names[0]
        return (0, actual_segment_name)

    return (0, None)






#simple version:
#retrieve data values sent in last single self turn,
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnLastDataSentOld(update_digit_prob):
    global gl_turn_history
    last_self_data_sent = None
    for turn_i in range(0, len(gl_turn_history)):
        turn_tup = gl_turn_history[turn_i]
        if turn_tup[1] == 'partner':
            continue
        turn_da_list = turn_tup[2]
        turn_includes_InformTopicInfoItemValue = False
        for da in turn_da_list:
            da_print_string = da.getPrintString()
            if da_print_string.find('InformTopicInfo(ItemValue(') < 0:
                continue
            turn_includes_InformTopicInfoItemValue = True
            break
        if turn_includes_InformTopicInfoItemValue == True:
            last_self_data_sent = turn_da_list
            break
        else:
            print 'error updateBeliefInPartnerDataStateBasedOnLastDataSent() did not see any data DialogActs to base update on'
        
    if last_self_data_sent != None:
        #C8
        return updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(last_self_data_sent, update_digit_prob)
    else:
        return 0






    




#da_list probably consists of a single DialogAct, either 
#  InformTopicInfo(ItemValue(Digit(x1)))  or else
#  InformTopicInfo(ItemValue(DigitSequence(x1, x2, x3)))  
#where x1 will be a string digit value, e.g. 'one'
#The probability of this value is set to update_digit_prob, the remaining probability is set to ?,
#so update_digit_prob can be different for a check vs simple affirmation reply.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnDataValuesDialogActsOld(da_list, update_digit_prob):
    #print 'updateBeliefInPartnerDataStateBasedOnDataValuesDialogActs(da_list)'
    for da in da_list:
        da_print_string = da.getPrintString()
    #    print 'da: ' + da_print_string
        ds_index = da_print_string.find('ItemValue(DigitSequence(')
        if ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = da_print_string.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(da_print_string[start_index:rp_index])
            print 'updateBelief...digit_value_list: ' + str(digit_value_list)
            return updateBeliefInPartnerDataStateForDigitValueList(digit_value_list, update_digit_prob)
        d_index = da_print_string.find('ItemValue(Digit(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = da_print_string.find(')', start_index)
            digit_value = da_print_string[start_index:rp_index]
            print 'updateBelief...digit_value: ' + str(digit_value)
            return updateBeliefInPartnerDataStateForDigitValueList([digit_value], update_digit_prob)
        print 'updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs() identified no digits to update for da: ' + da_print_string
    return 0
    





#retrieve data values last discussed and stored as DialogActs in gl_most_recent_data_topic_da_list
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnMostRecentTopicDataOld(update_digit_prob):
    global gl_most_recent_data_topic_da_list

    print 'updateBeliefInPartnerDataStateBasedOnMostRecentTopicData()'
    print str(len(gl_most_recent_data_topic_da_list)) + ' das in gl_most_recent_data_topic_da_list: '
    for da in gl_most_recent_data_topic_da_list:
        print '  ' + da.getPrintString()

    if len(gl_most_recent_data_topic_da_list) == 0:
        return 0
    return updateBeliefInPartnerDataStateBasedOnDataValuesInDialogActs(gl_most_recent_data_topic_da_list, update_digit_prob)


#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#str_digit_list is a list of strings, e.g. ['one', 'six'...]
#The probability of this value is set to update_digit_prob, the remaining probability is set to ?,
#so update_digit_prob can be different for a check vs simple affirmation reply.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateForDigitValueListOld(str_digit_value_list, update_digit_prob):
    #print 'updateBeliefInPartnerDataStateForDigitList(' + str(str_digit_value_list) + ')'
    partner_dm = gl_agent.partner_dialog_model
    partner_index_pointer_advance_count = 0

    for digit_value in str_digit_value_list:
        partner_index_pointer_value = partner_dm.data_index_pointer.getDominantValue()
        partner_dm.data_model.setNthPhoneNumberDigit(partner_index_pointer_value, digit_value, update_digit_prob)
        partner_index_pointer_value += 1
        partner_index_pointer_advance_count += 1
        partner_dm.data_index_pointer.setAllConfidenceInOne(partner_index_pointer_value)

    return partner_index_pointer_advance_count

