#!/usr/bin/python -tt

#ruleProcessing.py is for reading in Otto-like rules, using the rules 
#to process input text to produce DialogActs, and using the rules to
#produce output text from DialogRules.
#
#A LogicalForm is of the form,   Predicate(LogicalForm, LogicalForm, ...)
#or                              Predicate
#
#A DialogAct is of the form,     Predicate(LogicalForm, LogicalForm, ...)
#but Predicate is drawn from a special set, called Intents.
#
#Thus two DialogActs might be:   RequestTopicInfo(receive-telephone-number)
#                                InformTD(IndexicalPosition(first))
#
#Version 2016/05/19:
#The version of 2016/05/19 should work well enough to support simple rules, but
#it should be significantly restructured.
#
#First, the distinction between DialogRules and Word Category rules is bogus.
#Every LogicalForm to utterance mapping is a Category rule.  It should be called
#an Utterance Category rule.
#A so-called DialogRule is actually an Utterance Category rule with the 
#utterance category being DialogRuleCat.  A DialogRuleCat is constrained to have
#an Intent as its lead predicate (aka a CommuncativeFunction in Otto).
#
#Second, every utterance mapping rule should allow recursion, or the inclusion of
#utterance category rules on the RHS enclosed by braces { }.
#
#Third, the rules should be segregated as Interpretive <- and Generator ->.
#An utterance rule rule can be both <->.
#This will allow designation of a preferred way of speaking a DialogAct that can
#be interpreted from several ways of saying it.
#
#Version 2016/06/04
#This version of 2016/06/04 addresses the third issue above.  Now we maintain
#separate sets of interpretation (<-) and generator (->) rules.  Like with Otto,
#a rule can also be both (<->).  This gives greater control over how things are
#said.  Generally, if there are alternative ways of expressing the same thing,
#there will be a bunch of interpretation rules <- and a single bidirectional 
#rule <-> which is the preferred output text.



import csv
import random
import sys
import copy
import re
import os
import math


gl_tell = False

def setTell(val):
    global gl_tell
    gl_tell = val



####################
#
#Test loop
#


gl_rules_dirpath = os.path.join(os.getcwd(), '..', 'rules')
#print 'and then... gl_rules_dirpath: ' + gl_rules_dirpath


#Test just the rules in isolated-rules-test.txt
def loopInputTest():
    initLFRules('isolated-rules-test.txt')
    loopInputMain()

    
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopInput():
    initLFRulesIfNecessary()
    loopInputMain()


def loopInputMain():
    input_string = raw_input('Input: ')
    input_string = removePunctuationAndLowerTextCasing(input_string)
    while input_string != 'stop' and input_string != 'quit':
        print '\n' + input_string
        res = applyLFRulesToString(input_string)
        if res == False:
            print 'no match'
        else:
            print 'MATCH: ' + str(res);
            da_list = parseDialogActsFromRuleMatches(res)
            reconstructed_text = ' '.join(generateTextFromDialogActs(da_list))
            print 'reconstructed: ' + reconstructed_text

        input_string = raw_input('\nInput: ')


def removePunctuationAndLowerTextCasing(text_data):
    text_data = text_data.lower()
    text_data = text_data.replace(',', '')
    text_data = text_data.replace('.', ' ')
    text_data = text_data.replace('!', '')
    text_data = text_data.replace('"', '')
    text_data = text_data.replace('?', '')
    text_data = text_data.replace('*', '')
    text_data = text_data.replace(':', '')
    text_data = text_data.replace('-', ' ')
    text_data = text_data.replace('  ', ' ')
    text_data = text_data.replace('~', '')
    text_data = text_data.replace('\\n', ' ')
    text_data = text_data.replace('=', ' ')     #added 2016/03/01
    return text_data




#
#
####################

####################
#
#Loading rules from the rules file
#


#gl_default_lf_rule_filename = 'tell-phone-number-lf-rules.txt'
gl_default_lf_rule_filename = 'tell-phone-number-lf-rules-2.txt'

#key: first-word-or-category-of-sequence:  value: (rule_lhs, rule_rhs)
#       where rule_lhs is a text representation of a DialogAct, which is Intent(LogicalForm)
#             rule_rhs is a list words or catgories
#
#Indexing from a string's first word is only needed for interpretation
gl_first_word_string_to_interpretation_rule_dict = {}


#key: intent predicate of the DialogAct
#value: a list of tuples for this intent: [(da, rhs), (da, rhs)...]
#where da is a DialogAct instance
#      rhs is a string of a list of words or category objects e.g. {PredCat[$1]}
gl_interpretation_dialog_act_rules = {}
gl_generator_dialog_act_rules = {}


#Word-categories are like in Otto, in terms of variables enclosed by brackets [$1]
#e.g. DigitCat[one] <-> one
#This allows a DialogAct rule to be:
#InformTD(ItemValue(Digit($1))) <-> {DigitCat[$1]}
#Where the {DigitCat[$1]} allows 'one' to generate the DialogAct:
#InformTD(ItemValue(Digit(one)))
#
#key: word-category-predicate              value: list of (wc-lhs, wc-rhs)
#where 
#    wc-lhs is word-category-predicate[arg]
#    wc-rhs is word tuple
# (wc-lhs, wc-rhs) constitutes a word-category rule
#e.g. 
# the Word-Category rules,   
#   'AreaCodeCat[area-code] <-> area code
#   'AreaCodeCat[bozotron-code] <-> bozotron code
# becomes the dictionary entry, 
#    { AreaCodeCat:[(AreaCodeCat[area-code], (area, code)),
#                   (AreaCodeCat[bozotron-code], (bozotron, code)) ]
#
gl_interpretation_word_category_rules = {}
gl_generator_word_category_rules = {}




gl_current_rules_filepath = None

def initLFRulesIfNecessary(lf_rule_filename = gl_default_lf_rule_filename):
    global gl_current_rules_filepath
    global gl_rules_dirpath
    
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    if gl_current_rules_filepath != filepath:
        initLFRules(lf_rule_filename)


def initLFRules(lf_rule_filename = gl_default_lf_rule_filename):
    global gl_current_rules_filepath
    global gl_rules_dirpath

    rules_filepath = gl_rules_dirpath + '/' + lf_rule_filename
    print 'tellPhoneNumber LF rules filepath: ' + rules_filepath
    gl_current_rules_filepath = rules_filepath
    compileStringToLFRuleDicts(rules_filepath)



def compileStringToLFRuleDicts(rules_filepath):
    file = open(rules_filepath, "rU")
    global gl_first_word_string_to_interpretation_rule_dict
    global gl_interpretation_dialog_act_rules
    global gl_generator_dialog_act_rules
    global gl_interpretation_word_category_rules
    global gl_generator_word_category_rules
    
    gl_first_word_string_to_interpretation_rule_dict = {}
    gl_interpretation_dialog_act_rules = {}
    gl_generator_dialog_act_rules = {}
    gl_interpretation_word_category_rules = {}
    gl_generator_word_category_rules = {}

    
    rule_text = ''
    interpretation_word_category_rule_list = []
    generator_word_category_rule_list = []
    interpretation_dialog_act_rule_list = []
    generator_dialog_act_rule_list = []
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
                (rule_lhs, rule_rhs, direction) = parseRuleLHSRHS(rule_text)
                lsb_index = rule_lhs.find('[')
                if lsb_index > 0:
                    if direction == '<->':
                        interpretation_word_category_rule_list.append((rule_lhs, rule_rhs))
                        generator_word_category_rule_list.append((rule_lhs, rule_rhs))
                    elif direction == '<-':
                        interpretation_word_category_rule_list.append((rule_lhs, rule_rhs))
                    elif direction == '->':
                        generator_word_category_rule_list.append((rule_lhs, rule_rhs))
                    else:
                        print 'error: compileStringToLFRuleDicts(' + rules_filepath + ') received unclear direction A ' + direction
                else:
                    if direction == '<->':
                        interpretation_dialog_act_rule_list.append((rule_lhs, rule_rhs))
                        generator_dialog_act_rule_list.append((rule_lhs, rule_rhs))
                    elif direction == '<-':
                        interpretation_dialog_act_rule_list.append((rule_lhs, rule_rhs))
                    elif direction == '->':
                        generator_dialog_act_rule_list.append((rule_lhs, rule_rhs))
                    else:
                        print 'error: compileStringToLFRuleDicts(' + rules_filepath + ') received unclear direction B ' + direction
            rule_text = ''
    file.close()

    for word_category_rule in interpretation_word_category_rule_list:
        parseAndAddWordCategoryRule(word_category_rule, gl_interpretation_word_category_rules)
    for word_category_rule in generator_word_category_rule_list:
        parseAndAddWordCategoryRule(word_category_rule, gl_generator_word_category_rules)

    for dialog_act_rule in interpretation_dialog_act_rule_list:
        parseAndAddDialogActRule(dialog_act_rule, gl_interpretation_dialog_act_rules, '<-')
    for dialog_act_rule in generator_dialog_act_rule_list:
        parseAndAddDialogActRule(dialog_act_rule, gl_generator_dialog_act_rules, '->')

    sortWordCategoryRulesByLength(gl_interpretation_word_category_rules)
    sortWordCategoryRulesByLength(gl_generator_word_category_rules)
    print '\nInterpretation WordCategory rules:'
    printAllWordCategoryRules(gl_interpretation_word_category_rules)
    print '\nGenerator WordCategory rules:'
    printAllWordCategoryRules(gl_generator_word_category_rules)
    print '\nInterpretation DialogAct rules:'
    printAllDialogActInterpretationRules()
    print '\nGenerator DialogAct rules:'
    printAllDialogActGeneratorRules()



#returns (rule_lhs, rule_rhs, direction) 
#where direction is one of '<-', '->', '<->'
def parseRuleLHSRHS(rule_text):
    big_number = 100000
    leftarrow_index = rule_text.find('<-')
    rightarrow_index = rule_text.find('->')
    both_index = rule_text.find('<->')

    if leftarrow_index < 0 and rightarrow_index < 0 and both_index < 0:
        print 'could not find arrow <-, ->, or <-> in rule_text: ' + rule_text
        return
    #index not found will be -1
    max_index = max(leftarrow_index+1, rightarrow_index+1, both_index+2)
    if leftarrow_index == -1:
        leftarrow_index = big_number
    if rightarrow_index == -1:
        rightarrow_index = big_number
    if both_index == -1:
        both_index = big_number
    min_index = min(leftarrow_index, rightarrow_index, both_index)

    lhs = rule_text[0:min_index]
    lhs = lhs.strip()
    rhs = rule_text[max_index+1:]
    rhs = rhs.strip()
    if both_index < big_number:
        return (lhs, rhs, '<->')
    elif leftarrow_index < big_number:
        return (lhs, rhs, '<-')
    elif rightarrow_index < big_number:
        return (lhs, rhs, '->')
    else:
        print 'error in parseRuleLHSRHS: could not identify direction in rule_text:' + rule_text
        return None
    


#returns (rule_lhs, rule_rhs)
#This obsolete version before 2016/06/04 does not distinguish <-, ->, <->
def parseRuleLHSRHS_Obsolete(rule_text):
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
    return (lhs, rhs)





#A Word-Category rules is a mapping:
#   Predicate[arg] <-> word1 word2...
def parseAndAddWordCategoryRule(str_rule_lhs_rhs, word_category_rules_dict):
    lhs = str_rule_lhs_rhs[0]
    rhs = str_rule_lhs_rhs[1]

    rhs = rhs.strip()
    rhs_words = rhs.split()
    rhs_words_tup = tuple(rhs_words)

    lsb_index = lhs.find('[')
    wcategory_predicate = lhs[0:lsb_index]
    this_wcategory_predicate_rule_list = word_category_rules_dict.get(wcategory_predicate)
    if this_wcategory_predicate_rule_list == None:
        this_wcategory_predicate_rule_list = []
        word_category_rules_dict[wcategory_predicate] = this_wcategory_predicate_rule_list
    this_wcategory_predicate_rule_list.append((lhs, rhs_words_tup))


#A DialogAct rule is a mapping:
#   Intent(LogicalForm) <-> word-or-word-category1 word-or-word-category2 ...
#The str_rule_lhs_hrls passed is a tuple (str_lhs, str_rhs)
#This turns the str_rhs into a tuple of either words or word-category predicates.
#This creates a rule, (str_lhs, (word_or_word_category_predicate, word_or_word_category_predicate, ...))
#Then, this picks off the first word_or_word_category_predicate from the rhs tuple.
#If this is a word, then this adds the rule to the gl_first_word_string_to_interpretation_rule_dict, with the
# key being that word.
#If the first element is a word_category_predicate, then this adds the rule to every first word
#of every arg version for the word_category having that predicate.
def parseAndAddDialogActRule(str_rule_lhs_rhs, dialog_act_rules_dict, direction):
    global gl_interpretation_word_category_rules
    global gl_first_word_string_to_interpretation_rule_dict
    #global gl_dialog_act_rules

    lhs = str_rule_lhs_rhs[0]
    rhs = str_rule_lhs_rhs[1]
    rhs = rhs.strip()
    #rhs can include word-categories like   {DigitCat[$8]}
    #Make sure these are separated by spaces just in case the rule writer did not include spaces
    #  {DigitCat[$8]}{DigitCat[$9]}
    rhs = rhs.replace('}', '} ')
    rhs = rhs.replace('{', ' {')

    da = parseDialogActFromString(lhs)
    da_list = dialog_act_rules_dict.get(da.intent)
    if da_list == None:
        da_list = []
        dialog_act_rules_dict[da.intent] = da_list
    da_list.append((da, rhs))

    #only need to deal with the gl_first_word_string_to_interpretation_rule_dict for rules
    #that serve in interpretation
    if direction == '->':
        return


    rhs_words = rhs.split()
    rhs_words_tup = tuple(rhs_words)
    first_word_or_cat = rhs_words[0]

    lbr_index = first_word_or_cat.find('{')
    first_words_to_index_under = []

    #If the first word of the word pattern is actually a word category, then we need to 
    #list this DialogRule under each first word of each arg version of that category 
    #  {predicate[$a]}
    if lbr_index >= 0:
        lsq_index = first_word_or_cat.find('[')
        predicate = first_word_or_cat[lbr_index+1:lsq_index]
        predicate = predicate.strip()

        cat_list = gl_interpretation_word_category_rules.get(predicate)
        if cat_list == None:
            print 'Problem in parseAndAddDialogActRule. Predicate ' + predicate + ' not found in word-cateogry dict'
            return
        #print 'cat_list: ' + str(cat_list)
        for cat_rule in cat_list:
            #print 'cat_rule: ' + str(cat_rule)
            rhs = cat_rule[1]
            first_word = rhs[0]
            #print 'first_word: ' + str(first_word)
            if not first_word in first_words_to_index_under:
                first_words_to_index_under.append(first_word)
    else:
        if not first_word_or_cat in first_words_to_index_under:
            first_words_to_index_under.append(first_word_or_cat)

    #print 'first_words_to_index_under: ' + str(first_words_to_index_under)

    for first_word_to_index_under in first_words_to_index_under:
        first_word_rule_list = gl_first_word_string_to_interpretation_rule_dict.get(first_word_to_index_under)
        if first_word_rule_list == None:
            first_word_rule_list = []
            gl_first_word_string_to_interpretation_rule_dict[first_word_to_index_under] = first_word_rule_list
        first_word_rule_list.append((lhs, rhs_words_tup))




#gl_interpretation_word_category_rules and gl_generator_word_category_rules are both dictionaries.
#   key: word-category-predicate   value: list of word-category rules with this predicate
#Different word-category rules share the same predicate but have different arg and 
#possibly different numbers of words in their text utterance.
#This runs through all of the word-category predicates in word_category_rules_dict, and
#for each one, it sorts its list of word-category rules from longest to shortest.
def sortWordCategoryRulesByLength(word_category_rules_dict):
    for predicate in word_category_rules_dict.keys():
        rule_list = word_category_rules_dict.get(predicate)
        rule_list.sort(key = lambda wc_rule_tup: len(wc_rule_tup[1]))  # sorts in place, key is len of rhs of the rule
        rule_list.reverse()


def printAllWordCategoryRules(word_category_rules_dict):

    for predicate in word_category_rules_dict.keys():
        print 'predicate: ' + predicate
        rule_list = word_category_rules_dict.get(predicate)
        for rule in rule_list:
            print '    '  + str(rule)


def printAllDialogActInterpretationRules():
    global gl_first_word_string_to_interpretation_rule_dict

    for rule_key in gl_first_word_string_to_interpretation_rule_dict.keys():
        print rule_key
        rule_list = gl_first_word_string_to_interpretation_rule_dict[rule_key]
        for rule in rule_list:
            print '    '  + str(rule)


def printAllDialogActGeneratorRules():
    global gl_generator_dialog_act_rules

    for da in gl_generator_dialog_act_rules.keys():
        rhs = gl_generator_dialog_act_rules.get(da)
        print '     ' + da + ' ' + str(rhs)


#
#
####################

####################
#
#DialogAct and LogicalForm classes, and 
#functions for parsing a LHS into a DialogAct instance
#


#LogicalForm intents
#
#InformTopicData
#RequestTopicData
#CheckTopicData
#ConfirmTopicData
#CorrectionTopicData
#
#InformDM    DM = DialogManagement
#RequestDM
#CheckDM
#ConfirmDM
#CorrectionDM
#

class LogicalForm():
    def __init__(self, predicate):
        predicate = predicate.strip()
        self.predicate = predicate   #If there are args, then this will be uppercase.  If this is an itself just an argument,
                                     #then this is likely to be lowercase.
        self.print_string = None
        self.arg_list = []

    def getPredicate(self):
        return self.predicate

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        if self.print_string != None:
            return self.print_string
        print_string = self.predicate + ''
        if len(self.arg_list) > 0:
            print_string += '('
            argsep = ''
            for arg in self.arg_list:
                arg_str = arg.getPrintString()
                print_string += argsep 
                print_string += arg_str
                argsep = ', '                #note the space after the comma
            print_string += ')'
        self.print_string = print_string
        return print_string


class DialogAct(LogicalForm):
    def __init__(self, intent):
        intent = intent.strip()
        self.intent = intent
        self.arg_list = []

    def getPredicate(self):
        return self.intent

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        print_string = self.intent + ''
        if len(self.arg_list) > 0:
            print_string += '('
            argsep = ''
            for arg in self.arg_list:
                arg_str = arg.getPrintString()
                print_string += argsep 
                print_string += arg_str
                argsep = ', '         #note the space after the comma
            print_string += ')'
        return print_string



#rule_match_list is a list of tuples, (str_dialog_act, start_index, end_index)
#Returns a list of DialogActs
def parseDialogActsFromRuleMatches(rule_match_list):
    da_list = []
    for match_tuple in rule_match_list:
        str_dialog_act = match_tuple[0]
        da = parseDialogActFromString(str_dialog_act)
        da_list.append(da)

    return da_list
    
    

#str_dialog_act is of the form, 
#   Predicate(LogicalForm, LogicalForm, ...)
#
def parseDialogActFromString(str_dialog_act):
    #print 'parseDialogActFromString(  ' + str_dialog_act + '  )'
    lp_index = str_dialog_act.find('(')
    intent = str_dialog_act[0:lp_index]
    #print 'lp_index: ' + str(lp_index) + '  intent: ' + intent
    da = DialogAct(intent)
    arg_str = str_dialog_act[lp_index+1:len(str_dialog_act)-1]
    #print 'arg_str: ' + arg_str
    str_arg_list = parsePredicatesWithArgs(arg_str)
    #print 'str_arg_list: ' + str(str_arg_list)

    lf_arg_list = []
    #print 'lf_arg_list: ' + str(lf_arg_list)
    for str_arg in str_arg_list:
        #print 'str_arg: ' + str_arg
        lf_arg = parseLogicalFormFromString(str_arg)
        lf_arg_list.append(lf_arg)
    da.arg_list = lf_arg_list
    return da


def parseLogicalFormFromString(str_lf):
    #print 'parseLogicalFormFromString(  ' + str_lf + '  )'
    lp_index = str_lf.find('(')
    if lp_index < 0:
        lf = LogicalForm(str_lf)
        #print 'found primitive lf: ' + lf.getPrintString()
        return lf
    predicate = str_lf[0:lp_index]
    predicate = predicate.strip()
    lf = LogicalForm(predicate)
    arg_str = str_lf[lp_index+1:len(str_lf)-1]
    str_arg_list = parsePredicatesWithArgs(arg_str)
    #print 'str_arg_list: ' + str(str_arg_list)
    lf_arg_list = []
    for str_arg in str_arg_list:
        #print '   str_arg: ' + str_arg
        lf_arg = parseLogicalFormFromString(str_arg)
        lf_arg_list.append(lf_arg)
    lf.arg_list = lf_arg_list
    return lf



#str_preds_args is a string of the form, 
#  lf1, lf2, lf3...
# where each lf is a LogicalForm that could be nested,  pred(lf, lf, lf) 
#This returns a list, [lf1, lf2, lf3...]
#where each lfX is a string representation of a LogicalForm that could be nested
# e.g.
#  'pred1(pred1a(pred1aa(pred1aaa, pred1aab), pred1ab(pred1aba, pred1abb)), pred1b), pred2(pred2a(pred2aa, pred2ab))'
#  returns [  'pred1(pred1a(pred1aa(pred1aaa, pred1aab), pred1ab(pred1aba, pred1abb)), pred1b)', 
#             'pred2(pred2a(pred2aa, pred2ab))' ]
def parsePredicatesWithArgs(str_preds_args):
    
    last_idx = 0
    lp_idx = str_preds_args.find('(', last_idx)
    comma_idx = str_preds_args.find(',', last_idx)
    str_arg_list = []
    
    #print 'parsePredicatesWithArgs( ' + str_preds_args + ' )'
    #print ' lp_idx: ' + str(lp_idx) + ' comma_idx: ' + str(comma_idx)

    while lp_idx > 0 or comma_idx > 0:
        #comma demarks the next arg
        if lp_idx < 0 or (comma_idx >0 and comma_idx < lp_idx):
            key_idx = comma_idx
            arg = str_preds_args[last_idx:key_idx]
            arg = arg.strip()
            str_arg_list.append(arg)
            last_idx = key_idx+1
            lp_idx = str_preds_args.find('(', last_idx)
            comma_idx = str_preds_args.find(',', last_idx)

        #next arg is a predicate with parens
        elif comma_idx < 0 or (lp_idx > 0 and lp_idx < comma_idx):
            key_idx = lp_idx
            paren_count = 1
            
            while paren_count > 0:
                key_idx += 1
                if key_idx >= len(str_preds_args):
                    print 'error parsePredicatesWithArgs found unbalanced parentheses ' + str_preds_args
                    return []
                if str_preds_args[key_idx] == '(':
                    paren_count += 1
                if str_preds_args[key_idx] == ')':
                    paren_count -= 1

            arg = str_preds_args[last_idx:key_idx+1]  #include the ')'
            arg = arg.strip()
            #print 'appending ' + arg
            str_arg_list.append(arg)
            key_idx += 1
            if key_idx >= len(str_preds_args):
                return str_arg_list
            last_idx = key_idx+1
            lp_idx = str_preds_args.find('(', last_idx)
            comma_idx = str_preds_args.find(',', last_idx)

        #debugging
        #print 'str_arg_list: ' + str(str_arg_list) + ' last_idx: ' + str(last_idx) 
        #        input_string = raw_input('\nPausing: ')
        #if input_string == 'quit':
        #    break

    if last_idx < len(str_preds_args):
        arg = str_preds_args[last_idx:]
        str_arg_list.append(arg)
    return str_arg_list



#
#
####################


####################
#
#Interpretion of text input using rules
#        
#This works in terms only of gl_first_word_string_to_interpretation_rule_dict 
#which uses a tuple (lhs, rhs) version of the rules, where lhs and rhs are strings.
#This does not use the DialogAct or LogicalForm classes.
#That would be an alternative way of doing it but it doesn't seem necessary.
#

#Assumes the rule set has already been loaded by initLFRulesIfNecessary() or a related function.
def applyLFRulesToString(input_string):
    global gl_first_word_string_to_interpretation_rule_dict
    global gl_tell

    word_list = input_string.split()
    i_word = 0;
    
    fit_rule_list = []    #a list of rule fits to the_string: [(DialogAct, start_i, end_i),...]
    while i_word < len(word_list):
        word_i = word_list[i_word]
        possible_rules = gl_first_word_string_to_interpretation_rule_dict.get(word_i)
        #print '\'' + word_i + '\':   possible_rules: ' + str(possible_rules)
        if possible_rules != None:
            for possible_rule in possible_rules:
                #print 'possible_rule: ' + str(possible_rule)
                #fit_tuple is (dialog_rule, i_word_start, i_word_end)  
                fit_tuple = testRuleOnInputWordsAtWordIndex(possible_rule, word_list, i_word)
                if fit_tuple != None:
                    fit_rule_list.append(fit_tuple)
                    #print 'fit_tuple: ' + str(fit_tuple)
        i_word += 1

    if gl_tell:
        print 'found ' + str(len(fit_rule_list)) + ' matches'
    res = selectMaximallyCoveringRules(fit_rule_list, len(word_list))
    if gl_tell:
        print 'narrowed down to ' + str(len(res)) + ' matches'
    return res



#fit_rule_list is a list of tuples: (DialogAct, start_index, stop_index)
#where start_index and stop_index are indices into a word list for input text 
#Some of the tuples could overlap and claim the same words.
#This function selects the longest (most-word) fitting tuples in a greedy fashion
#Returns a list of tuples which is a subset of the tuples passed
#
#Right now, this does not allow muliple DialogActs to 
#apply to the same set of words, so it does not return two interpretations of the same input
#.e.g. both InformTD and ConfirmTD.
#
def selectMaximallyCoveringRules(fit_rule_list, input_length):
    global gl_tell    
    print 'gl_tell: ' + str(gl_tell)

    if gl_tell:
        print 'selectMaximallyCoveringRules()  input_length: ' + str(input_length) + ' ' + str(len(fit_rule_list)) + ' rules'
        for fit_rule in fit_rule_list:
            print str(fit_rule)

    covered_word_flag_ar = [False] * input_length;
    res = []
    fit_rule_list.sort(key = lambda tup: tup[2]-tup[1])
    fit_rule_list.reverse()
    for fit_rule_tup in fit_rule_list:
        ok_p = True
        for ii in range(fit_rule_tup[1], fit_rule_tup[2]+1):
            if covered_word_flag_ar[ii] == True:
                ok_p = False
                break
        if ok_p == True:
            res.append(fit_rule_tup)
            for ii in range(fit_rule_tup[1], fit_rule_tup[2]+1):
                covered_word_flag_ar[ii] = True
    res.sort(key = lambda tup: tup[1])
    return res






#This applies all available rules to the word_list starting at i_word.
#rule is  (rule_rhs, rule_lhs)
#       where rule_rhs is a sequence of words or word-catgories
#             rule_lhs is a text representation of a DialogAct
#
#It is assumed that the first word of the rule_rhs matches the i_word of word_list.
#rule_lhs might have arguments like $1 which will get filled in from matches of word-categories
#to the word_list.
#If an element in rule_rhs is enclosed by braces { } then it is a reference to a word-category.
#Then each member of that word-category is looked up and tested against the string starting at
#i_word.  If a match is found, then the variable $1 for that word-category is made available
#for setting the argument value for that variable in the rule_lhs
#
#This returns a list: [ (str_DialogAct, i_word, i_next_word), ...]
#str_DialogAct means that it is not an actual DialogAct instance, but the string counterpart of one.
#The str_DialogAct's arguments will be filled in with values from any Word-Categories that were used
#i_word and i_next_word in the tuple tell what part of the word_list is spanned by the str_DialogAct.
def testRuleOnInputWordsAtWordIndex(rule, word_list, i_word_start):
    global gl_interpretation_word_category_rules

    #print ' testRuleOnInputWordsAtWordIndex(' + str(rule) + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'
    rule_rhs_items = rule[1]
    arg_index_map = {}    #key: $X where X is an argument indicator, value:  a predicate provided by a word-category
                          #that will substitute for $X in the DialogAct returned (if it matches)
    i_word = i_word_start
    i_rule = 0
    #print ' rule_rhs_items: ' + str(rule_rhs_items)
    while True:   #march along until either the end of the dialog rule word list or the input word list is exhausted, 
                  #This test is below.
        rule_word_or_word_category = rule_rhs_items[i_rule]
        #print '  test: ' + str(i_word) + ': ' + rule_word_or_word_category

        #rule_word_or_word_category is either a word or else an indicator of a word-category, like, {DigitCat[$1]}
        if rule_word_or_word_category.find('{') == 0:
            lbr_index = rule_word_or_word_category.find('[')
            word_category_predicate = rule_word_or_word_category[1:lbr_index]
            word_category = gl_interpretation_word_category_rules.get(word_category_predicate)
            if word_category == None:
                print 'error testRuleOnInputWordsAtWordIndex() could not find word-category ' + word_category_predicate
                i_word += 1
                continue
            (num_words_consumed, word_category_arg) = testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, 
                                                                                              word_list, i_word)
            #print 'testWordCategory can consume ' + str(num_words_consumed) + ' words'
            #The word_category_arg tell which arg version of the Word-Category matched
            #If the rule_word_or_word_category has a settable argument $arg_name,  then stuff a map.
            #If the rule_word_or_word_category has a specified argument, then only accept the match if it matches
            # word_category_arg
            if num_words_consumed > 0:
                lsb_index = rule_word_or_word_category.find('[')

                #No args case, just a predicate
                if lsb_index < 0:
                    i_word += num_words_consumed
                    i_rule += 1
                elif rule_word_or_word_category[lsb_index+1] == '$':
                    rsb_index = rule_word_or_word_category.find(']')
                    arg_name = rule_word_or_word_category[lsb_index+2:rsb_index]
                    arg_index_map[arg_name] = word_category_arg
                    i_word += num_words_consumed
                    i_rule += 1
                else:
                    rsb_index = rule_word_or_word_category.find(']')
                    arg_name = rule_word_or_word_category[lsb_index+1:rsb_index]
                    if word_category_arg == arg_name:
                        i_word += num_words_consumed
                        i_rule += 1
                    else:
                        #print 'matched arg ' + word_category_arg + ' does not match required arg ' + arg_name
                        return None                        
            else:
                #if we're looking for a word category, allow intervening words
                i_word += 1
        else:
            if i_word >= len(word_list):
                #print 'ran out of words A'
                return None
            #if a word-to-word match, then advance
            #print 'word_list[' + str(i_word) + ']:' + word_list[i_word]  + ' rule_word_or_word_cat: ' + str(rule_word_or_word_category)
            if word_list[i_word] == rule_word_or_word_category:
                i_word += 1
                i_rule += 1
            #if a word-to-word non-match, then this rule doesn't apply
            else:
                #print 'word-to-word non-match ' + word_list[i_word] + ' : ' + rule_word_or_word_category
                return None


        #the DialogAct matches
        if i_rule >= len(rule_rhs_items):
            #print '\n****DialgAct matches: i_word: ' + str(i_word) + ' i_rule: ' + str(i_rule)
            break

        if i_word > len(word_list):  # >= or > ?
            #print 'ran out of words B'
            return None

    #print 'still going with rule ' + str(rule) + ' word_list: ' + str(word_list) + ' i_word: ' + str(i_word) + ' i_rule: ' + str(i_rule)

    rule_dialog_act = rule[0]
    d_index = rule_dialog_act.find('$')
    while d_index > 0:
        #need to parse out forms:  ($1); ($1, $2, $3)
        comma_index = rule_dialog_act.find(',', d_index+1)
        rp_index = rule_dialog_act.find(')', d_index+1)
        if comma_index > 0 and comma_index > d_index+1 and comma_index < rp_index:
            rp_index = comma_index
        if rp_index < d_index:
            print 'error testRuleOnInputWordsAtWordIndex() found a minsmatched braces in a rule DialogAct: ' + rule_dialog_act
            return None
        da_arg_name = rule_dialog_act[d_index+1:rp_index]
        word_category_arg = arg_index_map.get(da_arg_name)
        if word_category_arg != None:
            rule_dialog_act = rule_dialog_act[0:d_index] + word_category_arg + rule_dialog_act[rp_index:]
        d_index = rule_dialog_act.find('$', rp_index+1)
    #print 'returning ' + str((rule_dialog_act, i_word_start, i_word)) + '\n'
    return (rule_dialog_act, i_word_start, i_word-1)




#Tests all arg versions of the word_category for the word_category_predicate passed on the 
#word_list starting at i_word
#If there's a word-by-word match for all words in the word tuple of a word-category, then
#that arg is returned along with that word_category's length (number of words)
#Preferably, the list of word_categories in gl_interpretation_word_category_rules would have been sorted by 
#length so that the longest possible match is returned
#returns (num_words_consumed, word_category_arg)
def testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, word_list, i_word_start):
    global gl_interpretation_word_category_rules
    
    if i_word_start >= len(word_list):
        return (0, None)

    word_category_rules = gl_interpretation_word_category_rules.get(word_category_predicate)

    #print 'testWordCategoryOnInputWordsAtWordIndex(' + word_category_predicate + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'

    wc_rule_list = gl_interpretation_word_category_rules.get(word_category_predicate)
    if wc_rule_list == None:
        print 'problem in testWordCategoryOnInputWordsAtWordIndex() no wc rules for predicate ' + word_category_predicate
        return (0, None)

    for wc_rule in wc_rule_list:
        rhs = wc_rule[1]  #a tuple of words 

        i_word = i_word_start
        i_wc_word = 0
        match_p = True
        while i_wc_word < len(rhs) and i_word < len(word_list):
            word_i = word_list[i_word]
            wc_word = rhs[i_wc_word]
            if word_i != wc_word:
                match_p = False
                break
            i_word += 1
            i_wc_word += 1
        if match_p:
            if i_wc_word < len(rhs):
                #print 'testWordCategory... rhs: ' + str(rhs) + ' ran out of words in word_list ' + str(word_list) + ' i_wc_word: ' + str(i_wc_word)
                return (0, None)

            lhs = wc_rule[0]
            lsb_index = lhs.find('[')
            rsb_index = lhs.find(']')
            wc_arg = lhs[lsb_index+1:rsb_index]
            #print 'testWordCategory...' + word_category_predicate + ' returning (' + str(len(rhs)) + ', ' + wc_arg + ')'
            return ( len(rhs), wc_arg)

    return (0, None)


#
#
####################

####################
#
#Generator rules
#

def generateTextFromDialogActs(da_list):
    word_list = []
    for da in da_list:
        da_word_list = generateTextFromDialogAct(da)
        if da_word_list == None:
            print 'error could not generate text from DialogAct ' + da.getPrintString()
        else:
            word_list.extend(da_word_list)
    return word_list



#dialog_act is an instance of a DialogAct
#Where each LogicalForm is itself a predicate or predicate(lf1, lf2...)
#The most interesting thing this function does is fill in the free arguments $1, $2 etc.
#from the DialogRule to the utterance.
#Returns a word_list of words generated by the gen_dialog_act passed.
def generateTextFromDialogAct(gen_dialog_act):
    global gl_generator_dialog_act_rules

    da_rule_list = gl_generator_dialog_act_rules.get(gen_dialog_act.intent)
    if da_rule_list == None:
        print 'error generateTextFromDialogAct() sees no rules for dialog_act ' + gen_dialog_act.getPrintString() + ' intent ' + gen_dialog_act.intent
        return None
    
    #Run through all of the LogicalForms and Word-Category rules that use this intent in its DialogAct.
    #Match predicte-by-predicate recursively.  As free arguments are encountered in the rule, map them
    #to argument values from the arguments of the generated LogicalForm.
    #XXXReturn the argument mapping for the first match to the dialog_act passed.
    #Prepare a list of all dialog rules that produce an argument mapping.
    arg_mapping_list = []
    #arg_mapping = None
    for da_rule in da_rule_list:
        rule_da = da_rule[0]
        arg_mapping = recursivelyMapDialogRule(rule_da, gen_dialog_act)
        if arg_mapping != None:
            arg_mapping_list.append((da_rule, arg_mapping))
            print ' matching gen rule: ' + da_rule[0].getPrintString() + ' arg_mapping: ' + str(arg_mapping)
    if len(arg_mapping_list) == 0:
        print 'error generateTextFromDialogAct() could not find a consistent recursive mapping for dialog_act\n '\
            + gen_dialog_act.getPrintString() + ' intent ' + gen_dialog_act.intent
        print 'da: ' + gen_dialog_act.getPrintString()
        return None


    #choose the DialogRule with the shortest arg_mapping because that is most specific, the one
    #with the fewest free parameters
    min_arg_mapping_len = 10000
    da_rule = None
    arg_mapping = None
    for da_rule_and_mapping in arg_mapping_list:
        this_da_rule = da_rule_and_mapping[0]
        this_arg_mapping = da_rule_and_mapping[1]
        if len(this_arg_mapping) < min_arg_mapping_len:
            min_arg_mapping_len = len(this_arg_mapping)
            da_rule = this_da_rule
            arg_mapping = this_arg_mapping
    
    print ' finally chose matching gen rule: ' + da_rule[0].getPrintString() + ' arg_mapping: ' + str(arg_mapping)

    word_list = []
    rhs = da_rule[1]
    rhs_list = rhs.split()
    print 'rhs: ' + str(rhs)
    for word_or_word_category in rhs_list:
        if word_or_word_category[0] == '{':
            lsb_index = word_or_word_category.find('[')
            rsb_index = word_or_word_category.find(']', lsb_index)
            wc_predicate = word_or_word_category[1:lsb_index]
            #print 'word_or_word_category: ' + str(word_or_word_category)
            if word_or_word_category[lsb_index+1] == '$':
                arg_name = word_or_word_category[lsb_index+2:rsb_index]
                arg_value = arg_mapping.get(arg_name);
                if arg_value == None:
                    print 'error arg_name ' + arg_name + ' not found in mapping ' + str(arg_mapping)
                    arg_value = ' [processing error] '
            else:
                arg_value = word_or_word_category[lsb_index+1:rsb_index]
            word_cat_rhs_word_tup = lookupWordCategoryRHSWords(wc_predicate, arg_value)
            #print 'extending word_list ' + str(word_list) + ' with ' + str(word_cat_rhs_word_tup)
            word_list.extend(word_cat_rhs_word_tup)
            #print 'word_list is now ' + str(word_list)
        else:
            #print 'appending word_list ' + str(word_list) + ' with ' + str(word_or_word_category)
            word_list.append(word_or_word_category)
            #print 'word_list is now ' + str(word_list)

    return word_list


#A word-category is of the form  predicate[arg-value]
#This looks up the word-category in the gl_generator_word_category_rules dictionary, then selects
#The correct version for the arg_value.
#This returns a tuple of words which is the rhs of that word-category
def lookupWordCategoryRHSWords(wc_predicate, arg_value):
    global gl_generator_word_category_rules
    wc_rule_list = gl_generator_word_category_rules.get(wc_predicate)
    if wc_rule_list == None:
        print 'error lookupWordCategoryRHSWords(' + wc_predicate + ', ' + arg_value + ') found no items' 
        return ''
    
    target_lhs = wc_predicate + '[' + arg_value + ']'
    for wc_rule in wc_rule_list:
        lhs = wc_rule[0]
        if lhs == target_lhs:
            rhs = wc_rule[1]
            return rhs
    print 'error lookupWordCategoryRHSWords(' + wc_predicate + ', ' + arg_value + ') found the predicate but no match to the arg_value'
    return ''


gl_tell_map = False

def setTellMap(val):
    global gl_tell_map
    gl_tell_map = val

#recursively checks all predicates and argugments of the template rule_da against the 
#generated DialogAct gen_da.  
#Fills in an argument map as it goes, leaving off the dollar signs.
#If successful match, then returns the argument_map.
#If something doesn't match, then this returns None.
def recursivelyMapDialogRule(rule_da, gen_da):
    if gl_tell_map:
        print '\nrule_da: ' + rule_da.getPrintString()
        print 'gen_da: ' + gen_da.getPrintString()
    arg_mapping = {}
    ok_p = recursivelyMapDialogRuleAux(rule_da, gen_da, arg_mapping)
    if ok_p:
        return arg_mapping
    else:
        return None
    
def recursivelyMapDialogRuleAux(rule_da, gen_da, arg_mapping):
    if gl_tell_map:
        print '\nrecurse'
        print 'rule_da: ' + rule_da.getPrintString()  + ' len(rule_da.arg_list): ' + str(len(rule_da.arg_list))
        print 'gen_da: ' + gen_da.getPrintString()

    if type(rule_da) != type(gen_da):
        if gl_tell_map:
            print 'type(rule_da) ' + str(type(rule_da)) + ' != type(gen_da) ' + str(type(gen_da))
        return False
    if len(rule_da.arg_list) != len(gen_da.arg_list):
        if gl_tell_map:
            print 'len(rule_da.arg_list) ' + str(len(rule_da.arg_list)) + ' != len(gen_da.arg_list) ' + str(len(gen_da.arg_list))
        return False

    if rule_da.getPredicate() != gen_da.getPredicate():
        d_index = rule_da.predicate.find('$')
        if d_index == 0:
            arg_name = rule_da.predicate[1:]
            arg_value = gen_da.predicate
            arg_mapping[arg_name] = arg_value
            if gl_tell_map:
                print 'Match! adding mapping [' + arg_name + ']=' + arg_value
            return True
        if gl_tell_map:
            print 'rule_da.predicate ' + rule_da.getPredicate() + ' != gen_da.predicate ' + gen_da.getPredicate()
        return False

    if len(rule_da.arg_list) == 0:
        if gl_tell_map:
            print 'Match! ' + rule_da.predicate + ' = ' + gen_da.predicate + ' and no args'
        return True
        #Not sure this section is necessary since we do the predicate test above
        #d_index = rule_da.predicate.find('$')
        #if d_index == 0:
        #    arg_name = rule_da.predicate[1:]
        #    arg_value = gen_da.predicate
        #    if gl_tell_map:
        #        print 'BBBadding arg_mapping[' + arg_name + '] = ' + arg_value
        #    arg_mapping[arg_name] = arg_value
        #    if gl_tell_map:
        #        print 'BBBMatch! adding mapping [' + arg_name + ']=' + arg_value
        #    return True
        #else:
        #    if rule_da.predicate == gen_da.predicate:
        #        if gl_tell_map:
        #            print 'Match! ' + rule_da.predicate + ' = ' + gen_da.predicate
        #        return True
        #    else:
        #        if gl_tell_map:
        #            print 'rule_da.predicate \'' + rule_da.predicate + '\' != gen_da.predicate \'' + gen_da.predicate + '\''
        #        return False
    else:
        for i in range(0, len(rule_da.arg_list)):
            rule_da_arg = rule_da.arg_list[i]
            gen_da_arg = gen_da.arg_list[i]
            if type(rule_da_arg) != type(gen_da_arg):
                if gl_tell_map:
                    print 'arg ' + str(i) + ': type(rule_da_arg) ' + str(type(rule_da_arg)) + ' != type(gen_da_arg) ' + str(type(gen_da_arg))
                return False
            elif type(rule_da_arg) != str:
                if gl_tell_map:
                    print 'rule_da_arg: ' + rule_da_arg.getPrintString() + ' is type ' + str(type(rule_da_arg)) + ' not str so recursing'
                vv =  recursivelyMapDialogRuleAux(rule_da_arg, gen_da_arg, arg_mapping)
                if vv == False:
                    return False
        if gl_tell_map:
            print 'Match! drop through recursion pop'
        return True






#
#
####################

