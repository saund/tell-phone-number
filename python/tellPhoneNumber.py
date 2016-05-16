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


#Use the cdm python project under this project organization
#dialog
# cdm
#  python
# tell-phone-number
#  python
cdm_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'cdm', 'python'))

print 'cdm_path: ' + cdm_path
sys.path.append(cdm_path)

from patternMatchj import *
#import patternMatchj as pm

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
    


