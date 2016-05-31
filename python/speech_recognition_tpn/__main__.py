import speech_recognition as sr

r = sr.Recognizer()
m = sr.Microphone()

try:
    #print("A moment of silence, please...")
    print("input an energy_threshold or type return to call r.adjust_for_ambient_noise(source)")
    input_string = raw_input('\nInput: ')
    val = None
    if input_string != None:
        try:
            val = int(input_string)
        except:
            print 'did not get that input'
    print 'val is : ' + str(val)
    if val == None:
        with m as source: r.adjust_for_ambient_noise(source)
    else:
        r.dynamic_energy_threshold = False
        r.energy_threshold = val
    #with m as source: r.adjust_for_ambient_noise(source)
    print("Set minimum energy threshold to {}".format(r.energy_threshold))

    r.pause_threshold = .3
    r.non_speaking_duration = min(r.non_speaking_duration, r.pause_threshold)
    print("Recognizer pause_threhsold is now " + str(r.pause_threshold))
    while True:
        print("Say something!")
        with m as source: audio = r.listen(source)
        print("Got it! Now to recognize it...")
        try:
            # recognize speech using Google Speech Recognition
            value = r.recognize_google(audio)

            # we need some special handling here to correctly print unicode characters to standard output
            if str is bytes: # this version of Python uses bytes for strings (Python 2)
                print(u"You said {}".format(value).encode("utf-8"))
            else: # this version of Python uses unicode for strings (Python 3+)
                print("You said {}".format(value))
        except sr.UnknownValueError:
            print("Oops! Didn't catch that")
        except sr.RequestError as e:
            print("Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))
except KeyboardInterrupt:
    pass
