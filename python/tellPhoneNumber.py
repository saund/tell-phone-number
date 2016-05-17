#!/usr/bin/python -tt

#tellPhoneNumber.py is an intial start at a dialog management system to
#transmit structured data between a transmitter and a receiver using human
#conversational dialogue.


import csv
import random
import sys
import copy
import re
import os
import math


#No longer using cdm, we'll have our own Otto-like rule set and write our own string parser here.
##Use the cdm python project under this project organization
##dialog
## cdm
##  python
## tell-phone-number
##  python
#cdm_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'cdm', 'python'))
#
#print 'cdm_path: ' + cdm_path
#sys.path.append(cdm_path)
#
#from patternMatchj import *


#print 'gl_rules_dirpath: ' + gl_rules_dirpath

gl_rules_dirpath = os.path.join(os.getcwd(), '..', 'rules')

#print 'and then... gl_rules_dirpath: ' + gl_rules_dirpath



def loopInput():
    init('tell-phone-number-rules1.txt')
    input_string = raw_input('Input: ')
    while input_string != 'stop' and input_string != 'quit':
        print '\n' + input_string
        res = applyLFRulesToString(input_string)
        if res == False:
            print 'no match'
        else:
            print 'MATCH: ' + str(res);
        input_string = raw_input('\nInput: ')







gl_default_lf_rule_filename = 'tell-phone-number-lf-rules.txt'

#key: first-word-or-category-of-sequence:  value: (rule_rhs, rule_lhs)
#       where rule_rhs is a sequence of words or catgories
#             rule_lhs is a text representation of a LogicalForm
gl_first_word_string_to_rule_dict = {}

#Word categories are like in Otto, in terms of variables enclosed by brackets [$1]
#e.g. DigitCat[one] <-> one
#This allows a rule to be:
#InformTD(ItemValue(Digit($1))) <-> {DigitCat[$1]}
#Where the {DigitCat[$1]} allows 'one' to generate the DialogAct:
#InformTD(ItemValue(Digit(one)))

#key:  string: word-category-name[args]    value: list: word-list
#e.g.  'DigitCat[one]'                     [one]
gl_word_category_fw_dict = {}

#value: list: word-list             key:  string: word-category-name[args] 
#e.g.   [one]                       'DigitCat[one]'
gl_word_category_rv_dict = {}



def initLFRules(lf_rule_filename = gl_default_lf_rule_filename):
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    print 'tellPhoneNumber LF rules filepath: ' + filepath
    compileStringToLFRuleDict(filepath)



def compileStringToLFRuleDict(filepath):
    file = open(filepath, "rU")
    
    gl_first_word_string_to_rule_dict = {}
    rule_text = ''
    while True:
        text_line = file.readline()
        if not text_line:
            break
        hash_index = text_line.find('#')
        if hash_index == 0:
            continue
        elif hash_index > 0:
            text_line = text_line[0:hash_index]
        backslash_index = text_line.find('\\')
        if backslash_index > 0:
            text_line = text_line[0:backslash_index]
            rule_text += text_line
        else:
            rule_text += text_line
            if len(rule_text) > 1:
                parseAndAddRule(rule_text)
            rule_text = ''
    file.close()
    
    print '\ngl_all_rules:'
    printAllRules()


def parseAndAddRule(rule_text):
    leftarrow_index = rule_text.find('<')
    if leftarrow_index < 0:
        print 'could not find < in rule_text: ' + rule_text
        return
    rightarrow_index = rule_text.find('>')
    if rightarrow_index < 0:
        print 'could not find > in rule_text: ' + rule_text
        return
    lhs = rule_text[0:leftarrow_index]
    lhs = lhs.strip()
    rhs = rule_text[rightarrow_index+1:]
    rhs = rhs.strip()
    rule = (rhs, lhs)
    space_index = rhs.find(' ')
    if space_index > 0:
        first_string_or_category = rhs[0:space_index]
    else:
        first_string_or_category = rhs

    existing_list = gl_first_word_string_to_rule_dict.get(first_string_or_category)
    if existing_list == None:
        new_rule_list = [rule]
        gl_first_word_string_to_rule_dict[first_string_or_category] = new_rule_list
    else:
        existing_list.append(rule)


def printAllRules():
    for rule_key in gl_first_word_string_to_rule_dict.keys():
        rule = gl_first_word_string_to_rule_dict[rule_key]
        print rule_key + ' : '  + str(rule)




def applyLFRulesToString(input_string):
    word_list = input_string.split()
    word_index = 0;
    
    res = []    #a list of rule fits to the_string: [(DialogAct, start_i, end_i),...]
    while word_index < len(word_list):
        word_i = word_list[word_index]
        possible_rules = gl_first_word_string_to_rule_dict.get(word_i)
        for rule in possible_rules:
            rule_fit = testRuleOnInputWordsAtWordIndex(rule, word_list, word_i)
            if rule_fit != None:
                res.append(rule_fit)
    return res


#rule is  (rule_rhs, rule_lhs)
#       where rule_rhs is a sequence of words or catgories
#             rule_lhs is a text representation of a LogicalForm
def testRuleOnInputWordsAtWordIndex(rule, word_list, word_i):
    return None
        
        

    








#LogicalForm intents
#
#InformTopicData
#RequestTopicData
#CheckTopicData
#ConfirmTopicData
#
#InformDM    DM = DialogManagement
#RequestDM
#CheckDM
#ConfirmDM
#

class LogicalForm():
    def __init__(self):
        self.intent = ''
        self.type = ''
        self.data = None
        self.string = None


    def getPrintString(self):
        print_string = self.intent + '(' + self.type
        if self.data != None:
            print_string += ', ' + self.data + ')'
        else:
            print_string += ')'
        return print_string


class Actor():
    def __init__(self):
        self.name = None
        self.partner_name = None
        self.self_dialog_model = None
        self.partner_dialog_model = None
        self.send_receive_role = None

    def setRole(sender_or_receiver, phone_number=None):
        return None

    

#There will be one DialogModel for owner=self and one for owner=other-speaker
class DialogModel():
    def __init__(self):
        self.model_for = None       #one of 'self', 'partner'
        
        #for this application...
        self.data_model = None                   #A DataModel_USPhoneNumber
        self.data_index_pointer = None           #An OrderedMultinomialBelief: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

        #should be generic for all data communication applications
        self.readiness = None                    #A BooleanBelief: 1 = ready, 0 = not
        self.turn = None                         #A BooleanBelief: 1 = self, 0 = other-speaker
        self.protocol_chunck_size = None         #An OrderedMultinomialBelief: [1, 2, 3, 10]
        self.protocol_handshaking = None         #An OrderedMultinomialBelief: [1, 2, 3, 4, 5]  1 = never, 5 = every turn

    def printSelf():
        return None
        



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
        self.data_indices = {'area_code':[0,2],\
                             'prefix':[3,5],\
                             'last-four-digits':[6,9]}


    #phone_number_string is like '3452233487', i.e. ten digits in a row
    def setPhoneNumber(self, phone_number_string):
        if len(phone_number_string) != 10:
            print 'setPhoneNumber got a phone_number_string: ' + phone_number_string + ' that is not 10 digits long'
            return
        for i in range(0, 10):
            digit = phone_number_string[i]
            self.data_beliefs[i].setValueDefinite(digit)


    #digit_value is a string
    def setNthPhoneNumberDigit(self, nth, digit_value):
        self.data_beleifs[nth].setValueDefinite(digit_value)

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
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 0.0

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
        return '[ \'' + str(temp_list[0][0]) + '\':' + format(temp_list[0][1], '.2f') + ', \''\
            + str(temp_list[1][0]) + '\':' + format(temp_list[1][1], '.2f') + ', \''\
            + str(temp_list[2][0]) + '\':' + format(temp_list[2][1], '.2f') + ' ]'



#A BooleanBelief represents belief distributed between the value 0=false and 1=true
#In other words, this is a binomial.
class BooleanBelief():
    def __init__(self):
        self.true_confidence = .5  #belief in the value 1=true, initialize as totally unknown

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        return '[ ' + format(self.true_confidence, '.2f') + ' ]'
        


#An OrderedMultinomialBelief represents belief distributed between several ordered values.
class OrderedMultinomialBelief():
    def __init__(self):
        self.value_name_confidence_list = None   #each element is a list [value, confidence]

    def initEquallyDistributed(self, value_list):
        self.value_name_confidence_list = []
        conf = 1.0 / len(value_list)
        for i in range(0, len(value_list)):
            self.value_name_confidence_list.append([value_list[i], conf])

    def initAllConfidenceInOne(self, value_list, all_confidence_value):
        self.value_name_confidence_list = []
        for i in range(0, len(value_list)):
            this_value = value_list[i]
            if this_value == all_confidence_value:
                conf = 1.0
            else:
                conf = 0.0
            self.value_name_confidence_list.append([this_value, conf])


    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        conf_threshold_to_print = .1     #only print confidences > threshold .1
        temp_list = self.value_name_confidence_list[:]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        ret_str = '[ '
        ret_str += str(temp_list[0][0]) + ':' + format(temp_list[0][1], '.2f')
        i = 1;
        while i < 3:
            if temp_list[i][1] > conf_threshold_to_print:
                ret_str += ' / ' + str(temp_list[i][0]) + ':' + format(temp_list[i][1], '.2f')
            i += 1
        ret_str += ' ]'
        return ret_str



        
        

                        




