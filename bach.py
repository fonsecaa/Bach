import os
import pickle
import copy
from random import random, choice
from music21 import *

'''
CONSTANTS
'''
CURRENT_VERSION = 1.0

LOWEST_PITCH = 40
HIGHEST_PITCH = 84

RANGES = [[],[],[],[]]
[BASS,ALTO,TENOR,SOPRANO] = range(0,4)

RANGES[BASS] = range(LOWEST_PITCH,61)
RANGES[TENOR] = range(50,65)
RANGES[ALTO] = range(60,75)
RANGES[SOPRANO] = range(62,HIGHEST_PITCH+1)

'''
PUBLIC FUNCTIONS
'''
def gen_model(chord_order,pitch_order,offset_order):
    '''
    Builds a model based on Bach's chorales that are included
    as a part of music21.
    
    Note: This function may take a while to run
    
    INPUTS:
        chord_order: order of the markov model for the chord progression
        pitch_order: order of the markov model for the melody pitches
        offset_order: order of the markov model for rhythm in the form of offsets
    
    RETURNS:
        A model object encapsulating the three markov models
    '''
    bcl = corpus.chorales.ChoraleList()
    bwv = bcl.byBWV
    model = chorale_model(chord_order,pitch_order,offset_order)
    
    saved_model = _check_if_model_saved(model)
    
    if not saved_model:
        for key in bwv.keys():
            stream = corpus.parse('bach/bwv' + str(bwv[key]['bwv']))
            print 'Now parsing: ' + 'bach/bwv' + str(bwv[key]['bwv'])
            model.add_melody_pitches_to_model(stream)
            model.add_melody_offsets_to_model(stream)
            model.add_chords_to_model(stream)
            
        model.save_model()
            
    else:
        if not model.load_model(saved_model):
            for key in bwv.keys():
                stream = corpus.parse('bach/bwv' + str(bwv[key]['bwv']))
                print 'Now parsing: ' + 'bach/bwv' + str(bwv[key]['bwv'])
                model.add_melody_pitches_to_model(stream)
                model.add_melody_offsets_to_model(stream)
                model.add_chords_to_model(stream)
                
            model.save_model()
        
    return model

def gen_melody(model,melody_len):
    '''
    Generates a melody based on a model object.
    
    INPUTS:
        model: A model as generated by parse_bach
        melody_len: The desired length in notes of the melody
        
    RETURNS:
        A music21 Score opbject with a single part
        
        If gen_melody is unable to generate a melody of
        the specified length, gen_melody will return None
        and print an error
    '''
    pitch_constraint = [str(pitch.Pitch(x)) for x in RANGES[SOPRANO]]
    melody_pitches = _gen_melody_component(model.melody_pitch_model,model.melody_pitch_order,melody_len,pitch_constraint)
    
    count = 0
    while (melody_pitches == None):
        melody_pitches = _gen_melody_component(model.melody_pitch_model,model.melody_pitch_order,melody_len,pitch_constraint)
        count += 1
        
        if (count >= 1000):
            print 'Unable to generate specified melody'
        
    offset_constraint = None
    melody_offsets = _gen_melody_component(model.melody_offset_model,model.melody_offset_order,melody_len,offset_constraint)
    
    count = 0
    while (melody_offsets == None):
        melody_offsets = _gen_melody_component(model.melody_offset_model,model.melody_offset_order,melody_len,offset_constraint)
        count += 1
        
        if (count >= 1000):
            print 'Unable to generate specified melody'
    
    melody_durations = _get_melody_durations(melody_offsets)
    melody = zip(melody_pitches,melody_durations)
        
    soprano = stream.Stream()

    for melody_pitch, melody_duration in melody:
        if melody_pitch == 'REST':
            n = note.Rest()
        else:
            p = pitch.Pitch(melody_pitch)
            n = note.Note(p)

        n.duration = duration.Duration(melody_duration)
        soprano.append(n)
        
    return soprano
    
def gen_harmony(melody,model):
    '''
    Generates a four part harmony for a given melody using a model
    
    INPUTS:
        melody: music21 Score object containing one part
        model: A model as generated by parse_bach
        
    RETURNS:
        A music21 Score object with four parts in harmony
        
        If build_harmony is unable to generate a harmony
        from a given melody, build_harmony will return None
        and print an error
    '''
    chord_model = model.chord_model
    chord_model_order = model.chord_order
    chord_model_weights = model.chord_weights[()]
    
    [chord_prog_pitches,harmony_durations] = _gen_chord_prog(melody,chord_model,chord_model_order,chord_model_weights)

    harmony_pitches = []
    
    for (melody_note,chord) in zip(melody.notes,chord_prog_pitches):
        if len(harmony_pitches) == 0:
            prev_harmony = []
        else:
            i = -1
            prev_harmony = harmony_pitches[i]
            
            while (prev_harmony == 'REST'):
                i -= 1
                if (i >= len(harmony_pitches)):
                    prev_harmony = []
                    break
                else:
                    prev_harmony = harmony_pitches[i]
            
        if chord == 'REST':
            harmony_pitches.append(['REST','REST','REST','REST'])
        else:
            next_harmony = _get_next_harmony(prev_harmony,melody_note.pitch,chord)
            
            i = 0
            while (next_harmony == None):
                next_harmony = _get_next_harmony(prev_harmony,melody_note.pitch,chord)
                i += 1
                if i > 1000:
                    print 'Unable to realize harmony with given melody'
                    return
                    
            harmony_pitches.append(next_harmony)

    harmony_score = stream.Stream()
    bass_tenor_alto_streams = [stream.Part(),stream.Part(),stream.Part()]
    
    for (chord,chord_duration) in zip(harmony_pitches,harmony_durations):
        for (pitch,s) in zip(chord,bass_tenor_alto_streams):
            if pitch == 'REST':
                n = note.Rest()
            else:
                n = note.Note(pitch)
                
            n.duration = duration.Duration(chord_duration)
            s.append(n)
        
    t_clef = clef.TrebleClef()
    b_clef = clef.BassClef()
    t_clef.offset = 0.0
    b_clef.offset = 0.0
    
    melody.insert(0,t_clef)
    bass_tenor_alto_streams[2].insert(0,t_clef)
    bass_tenor_alto_streams[1].insert(0,b_clef)
    bass_tenor_alto_streams[0].insert(0,b_clef)
    
    harmony_score.insert(0,melody)
    harmony_score.insert(0,bass_tenor_alto_streams[2])
    harmony_score.insert(0,bass_tenor_alto_streams[1])
    harmony_score.insert(0,bass_tenor_alto_streams[0])
        
    return _smooth_harmony(harmony_score)
    
'''
PRIVATE FUNCTIONS
'''
def _gen_melody_component(element_model,model_order,melody_len,constraint):
    '''
    Generates a component of the melody i.e. the melody pitches
    or the melody offsets
    
    INPUTS:
        element_model: markov model for the given element
        model_order: order of element markov model
        melody_len: desired length of melody
        constrain: the set of possible options for an element in the melody
                   If constraint == None there is no restriction on what
                   elements can be in the melody
        
    RETURNS:
        A list of elements as generated by the element markov model
    '''
    melody_elements = []
    count = 0
    
    element_buff = tuple(['NULL' for x in range(model_order)])
    next_element = _get_next_element(element_model[element_buff])
    
    if constraint != None:
        i = 0
        while next_element not in constraint:
            next_element = _get_next_element(element_model[element_buff])
            i += 1
            if i > 100:
                return None
    else:
        next_element = _get_next_element(element_model[element_buff])
    
    while (count < melody_len):
        melody_elements.append(next_element)

        element_buff = element_buff[1:] + (next_element,)
        next_element = _get_next_element(element_model[element_buff])
        
        if constraint != None:
            i = 0
            while next_element not in constraint:
                next_element = _get_next_element(element_model[element_buff])
                i += 1
                if i > 100:
                    return None
        else:
            next_element = _get_next_element(element_model[element_buff])
            
        count += 1

        if (next_element == 'NULL'):
            return None
            
    return melody_elements

def _get_melody_durations(melody_offsets):
    '''
    Returns a list of note durations (quarter note, half note, etc.) 
    given a list of note offsets
    '''
    melody_durations = []
    
    for i in range(len(melody_offsets)-1):
        offset_delta = melody_offsets[i+1] - melody_offsets[i]

        if offset_delta < 0.0:
            offset_delta = (4 - melody_offsets[i]) + melody_offsets[i+1]

        melody_durations.append(offset_delta)
        
    return melody_durations
    
def _gen_chord_prog(melody,chord_model,chord_model_order,chord_weights):
    '''
    Returns a list of chords that form a chord progression to match the melody
    
    INPUTS:
        melody: melody on which the chord progression is based
        chord_model: markov model for chord progressions
        chord_model_order: order of chord markov model
        chord_weights: A dictionary of all chords used in the chord markov model
                       with the chords as keys and the frequency of use as values.
                       This is used as a fallback when the markov model is unable
                       to produce a chord for a given note in the melody
    
    RETURNS:
        list of chords where a chord is a tuple of notes eg. ('A','C','E')
    '''
    chord_prog = []
    chord_durations = []

    melody_pitches = melody.flat.notesAndRests
    chord_buff = tuple(['NULL' for x in range(chord_model_order)])
    
    for pitch in melody_pitches:
        if not pitch.isRest:
            if chord_buff in chord_model.keys():
                next_chord = _get_next_chord(pitch,chord_model[chord_buff],chord_weights)
            else:
                next_chord = _get_next_chord(pitch,chord_weights,chord_weights)
            if next_chord != 'NULL':
                chord_prog.append(next_chord)
                chord_durations.append(pitch.duration.quarterLength)
                
            chord_buff = chord_buff[1:] + (next_chord,)

        elif pitch.isRest:
            chord_prog.append(['REST'])
            chord_durations.append(pitch.duration.quarterLength)

    return [chord_prog,chord_durations]
    
def _get_next_chord(pitch,chord_model_state,chord_weights):
    '''
    Returns a chord given melody pitch and model state
    '''
    constrained_model = {next_state:chord_model_state[next_state] for next_state in chord_model_state.keys() if pitch.name in next_state}
    if len(constrained_model.keys()) == 0:
        constrained_model = {next_state:chord_weights[next_state] for next_state in chord_weights.keys() if pitch.name in next_state}
        
    next_element = _get_next_element(constrained_model)
    return next_element
    
def _get_next_harmony(prev_harmony,melody_pitch,chord_notes):
    '''
    Assigns pitches to each voice to create a single harmony given a previous harmony.
    If prev_harmony is empty then assign the bass to the root of the chord and randomly
    assign the alto and tenor within their respective ranges.
    
    INPUTS:
        prev_harmony: the previous harmony for the given state
        melody_pitch: melody pitch (aka the soprano pitch) for the given state
        chord_notes: chord for the given state in the chord progression
        
    RETURNS:
        list of pitches for the four parts [Bass,Tenor,Alto,Soprano]
    '''
    try:
        num_pitches = len(chord_notes)
        chord_notes_midi = _get_chord_base(chord_notes)
    
        assigned_pitches = [None,None,None,None]
        
        soprano_pitch = melody_pitch
        
        assigned_pitches[SOPRANO] = soprano_pitch
    
        pitch_options = [x for x in range(LOWEST_PITCH,soprano_pitch.midi) if x%12 in chord_notes_midi]
    
        if num_pitches == 4:
            for element in [x for x in pitch_options if x%12 == soprano_pitch.midi%12]:
                pitch_options.remove(element)
        
        if not prev_harmony:
            root = chord.Chord(chord_notes).findRoot()
            bass_pitch_midi = min([x for x in RANGES[BASS] if x%12 == root.midi%12])
            assigned_pitches[BASS] = pitch.Pitch(bass_pitch_midi)
            pitch_options.remove(bass_pitch_midi)
    
        else:
            valid_alto_pitch_options = _get_valid_pitch_options(prev_harmony,ALTO,assigned_pitches,pitch_options)
            alto_pitch_midi = _get_nearest_pitch(prev_harmony[ALTO],valid_alto_pitch_options)
            assigned_pitches[ALTO] = pitch.Pitch(alto_pitch_midi)
            pitch_options.remove(alto_pitch_midi)
        
        if not prev_harmony:
            if (num_pitches == 4) or (assigned_pitches[BASS].name == assigned_pitches[SOPRANO].name):
                for element in [x for x in pitch_options if x%12 == bass_pitch_midi%12]:
                    pitch_options.remove(element)
    
            for element in pitch_options:
                if element <= bass_pitch_midi:
                    pitch_options.remove(element)
                    
        elif (num_pitches == 4) or (assigned_pitches[ALTO].name == assigned_pitches[SOPRANO].name):
            for element in [x for x in pitch_options if x%12 == alto_pitch_midi%12]:
                pitch_options.remove(element)
    
            for element in pitch_options:
                if element > alto_pitch_midi:
                    pitch_options.remove(element)
        
        if not prev_harmony:
            alto_pitch_midi = choice([x for x in pitch_options if x in RANGES[ALTO]])
            assigned_pitches[ALTO] = pitch.Pitch(alto_pitch_midi)
            pitch_options.remove(alto_pitch_midi)
        else:
            valid_tenor_pitch_options = _get_valid_pitch_options(prev_harmony,TENOR,assigned_pitches,pitch_options)
            tenor_pitch_midi = _get_nearest_pitch(prev_harmony[TENOR],valid_tenor_pitch_options)
            assigned_pitches[TENOR] = pitch.Pitch(tenor_pitch_midi)
            pitch_options.remove(tenor_pitch_midi)
    
        if not prev_harmony:
            if (num_pitches == 4) or (assigned_pitches[BASS].name == assigned_pitches[SOPRANO].name):
                for element in [x for x in pitch_options if x%12 == alto_pitch_midi%12]:
                    pitch_options.remove(element)
        elif (num_pitches == 4) or (assigned_pitches[ALTO].name == assigned_pitches[SOPRANO].name):
            for element in [x for x in pitch_options if x%12 == tenor_pitch_midi%12]:
                pitch_options.remove(element)
            
        if not prev_harmony:
            if ((assigned_pitches[ALTO].name == assigned_pitches[SOPRANO].name) or
                (assigned_pitches[ALTO].name == assigned_pitches[BASS].name)):
                for element in [x for x in pitch_options if x%12 == soprano_pitch.midi%12]:
                    pitch_options.remove(element)
                for element in [x for x in pitch_options if x%12 == bass_pitch_midi%12]:
                    pitch_options.remove(element)
        else:
            if ((assigned_pitches[TENOR].name == assigned_pitches[SOPRANO].name) or
                (assigned_pitches[TENOR].name == assigned_pitches[ALTO].name)):
                for element in [x for x in pitch_options if x%12 == soprano_pitch.midi%12]:
                    pitch_options.remove(element)
                for element in [x for x in pitch_options if x%12 == alto_pitch_midi%12]:
                    pitch_options.remove(element)
    
        if not prev_harmony:
            for element in pitch_options:
                if element > alto_pitch_midi:
                    pitch_options.remove(element)
    
        else:
            for element in pitch_options:
                if element > tenor_pitch_midi:
                    pitch_options.remove(element)
        
        if not prev_harmony:
            tenor_pitch_midi = choice([x for x in pitch_options if x in RANGES[TENOR]])
            assigned_pitches[TENOR] = pitch.Pitch(tenor_pitch_midi)
        else:
            valid_bass_pitch_options = _get_valid_pitch_options(prev_harmony,BASS,assigned_pitches,pitch_options)
            bass_pitch_midi = _get_nearest_pitch(prev_harmony[BASS],valid_bass_pitch_options)
            assigned_pitches[BASS] = pitch.Pitch(bass_pitch_midi)
    except:
        return None
    
    return assigned_pitches
            
def _get_valid_pitch_options(prev_harmony,pending_part,assigned_pitches,pitch_options):
    '''
    Returns a list of valid pitches (as midi numbers) for a given part, given the preceeding
    harmony, what pitches have already been assigned and what pitch_options remain
    '''
    valid_pitch_options = [x for x in pitch_options if x in RANGES[pending_part]]
    
    for (part,part_pitch) in enumerate(assigned_pitches):
    
        if part_pitch != None:
            prev_interval = interval.notesToInterval(prev_harmony[pending_part],prev_harmony[part])
            
            if prev_interval.name[0] == 'P':
                pitch_shift = part_pitch.midi - prev_harmony[part].midi
                invalid_pitch = pitch.Pitch(prev_harmony[pending_part].midi + pitch_shift)
                
                if invalid_pitch in valid_pitch_options:
                    valid_pitch_options.remove(invalid_pitch)
            
    return valid_pitch_options
           
def _get_nearest_pitch(pitch,pitch_options):
    (dist,index) = min([(abs(pitch.midi - element),i) for (i,element) in enumerate(pitch_options)])
    return pitch_options[index]

def _get_chord_base(note_list):
    parsed_chord = chord.Chord(note_list)
    return [element.midi%12 for element in parsed_chord.pitches]
    
def _get_next_element(model_state):
    rand_val = random()
    weight = 0.0
    total = 0
    
    for key in model_state.keys():
        total += model_state[key]
    
    for key in model_state.keys():
        if rand_val >= weight:
            rv = key
        weight += float(model_state[key])/float(total)
            
    return rv
    
def _smooth_harmony(harmony):
    '''
    Given a harmony, _smooth_harmony iterates through each part combining
    consecutive notes with identical pitches into one note. This function
    ignores the melody (aka soprano) line.
    '''
    temp_harmony = copy.deepcopy(harmony)
    new_harmony = stream.Score()
    new_harmony.insert(0,temp_harmony.elements[0])

    for (i,harmony_part) in enumerate(temp_harmony.elements[1:]):
        temp_part = stream.Part()
        notes_and_rests = harmony_part.notesAndRests
        current_note = notes_and_rests[0]
        
        while (current_note != None):
            next_note = notes_and_rests.getElementAfterElement(current_note,[note.Note])
            while (next_note != None):
                if (current_note.fullName != next_note.fullName):
                    break
                current_note.quarterLength += next_note.quarterLength
                notes_and_rests.remove(next_note)
                next_note = notes_and_rests.getElementAfterElement(current_note,[note.Note])
                    
            current_note = notes_and_rests.getElementAfterElement(current_note,[note.Note])  

        for n in notes_and_rests:
            temp_part.append(n)
        new_harmony.insert(0,temp_part)
        
    return new_harmony
    
def _dict_to_file(dict,filename):
    success = True
    try:
        output = open(str(filename) + '.pkl','wb')
        pickle.dump(dict,output)
        output.close()
    except:
        print 'Error writing to' + str(filename) + '.pkl'
        success = False
        
    return success

def _file_to_dict(filename):
    rv = {}
    try:
        pkl_file = open(str(filename),'rb')
        rv = pickle.load(pkl_file)
        pkl_file.close()
    except:
        print 'Error reading from' + str(filename) + '.pkl'
        return None

    return rv
    
def _check_if_model_saved(model):
    '''
    Determines if a saved version of the specidied model exists.
    If so it returns the name of the save file.
    '''
    try:
        for file in os.listdir("."):
            if file.endswith(".pkl"):
                file_chord_order = file.strip('.pkl').split('_')[2]
                file_pitch_order = file.strip('.pkl').split('_')[3]
                file_offset_order = file.strip('.pkl').split('_')[4]
                file_model_version = file.strip('.pkl').split('_')[5]

                if ((file_chord_order == str(model.chord_order)) and
                    (file_pitch_order == str(model.melody_pitch_order)) and
                    (file_offset_order == str(model.melody_offset_order)) and
                    (file_model_version == str(CURRENT_VERSION))):
                    return file
    except:
        print 'No saved model found'
    return None
    
def _transpose_to_c(stream):
    num_sharps = stream.analyze('key').sharps
    num_half_steps = ((num_sharps*7) % 12)
    
    if num_half_steps > 6:
        num_half_steps = num_half_steps - 12
        
    return stream.transpose(-1*num_half_steps)

def _update_markov(data,markov_model,order):
    data.append('NULL')
    num_elements = len(data)
    
    for i in range(order):
        data.insert(0,'NULL')
        
    for i in range(num_elements):
        state = tuple(data[i:i+order])
        next_state = data[i+order]
        
        if state not in markov_model.keys():
            markov_model[state] = {}

        if next_state not in markov_model[state]:
            markov_model[state][next_state] = 1
        else:
            markov_model[state][next_state] += 1
            
    return markov_model
    
class chorale_model(object):

    def __init__(self,c_order,m_p_order,m_o_order):
        self.chord_order = c_order
        self.melody_pitch_order = m_p_order
        self.melody_offset_order = m_o_order
        self.melody_pitch_model = {}
        self.melody_offset_model = {}
        self.chord_model = {}
        self.chord_weights = {}
        
    def save_model(self):
        output = {}
        
        output['chord_order'] = self.chord_order
        output['melody_pitch_order'] = self.melody_pitch_order
        output['melody_offset_order'] = self.melody_offset_order
        output['melody_pitch_model'] = self.melody_pitch_model
        output['melody_offset_model'] = self.melody_offset_model
        output['chord_model'] = self.chord_model
        output['chord_weights'] = self.chord_weights
        
        filename = ('chorale_model_' + str(self.chord_order) + 
                    '_' + str(self.melody_pitch_order) + 
                    '_' + str(self.melody_offset_order) + 
                    '_' + str(CURRENT_VERSION))
        
        if _dict_to_file(output,filename):
            print 'Model successfully saved'

        else:
            print 'Error saving model'
        
    def load_model(self,filename):
        success = True
        input = _file_to_dict(filename)
        
        if input:
            try:
                self.chord_order = input['chord_order']
                self.melody_pitch_order = input['melody_pitch_order']
                self.melody_offset_order = input['melody_offset_order']
                self.melody_pitch_model = input['melody_pitch_model']
                self.melody_offset_model = input['melody_offset_model']
                self.chord_model = input['chord_model']
                self.chord_weights = input['chord_weights']
            except:
                print 'Error loading model'
                return None

            print 'Successfully loaded model'
            return success
        else:
            return None
        
    def add_chords_to_model(self,s):
        try:
            satb_stream = stream.Score()
            satb_stream.insert(0, s.getElementById('Soprano'))
            satb_stream.insert(0, s.getElementById('Alto'))
            satb_stream.insert(0, s.getElementById('Tenor'))
            satb_stream.insert(0, s.getElementById('Bass'))
        except:
            return
        
        parsed_chords = _transpose_to_c(satb_stream.chordify().flat.getElementsByClass('Chord'))
        chords = []
        
        if parsed_chords == None:
            return
            
        for chord in parsed_chords:
            if chord.duration.quarterLength >= 1.0:
                chord_pitches = tuple(sorted(set([str(element.name) for element in chord.pitches])))
                if len(chord_pitches) >= 3:
                    chords.append(chord_pitches)
        
        self.chord_model = _update_markov(chords,self.chord_model,self.chord_order)
        self.chord_weights = _update_markov(chords,self.chord_weights,0)

    def add_melody_pitches_to_model(self,s):
        try:
            soprano_stream = s.getElementById('Soprano').flat.notesAndRests
        except:
            return
            
        melody_pitches = []
    
        for element in _transpose_to_c(soprano_stream):
            if element.isRest:
                melody_pitches.append('REST')
            elif element.isNote:
                melody_pitches.append(str(element.pitch))
        
        self.melody_pitch_model = _update_markov(melody_pitches,self.melody_pitch_model,self.melody_pitch_order)
        
    def add_melody_offsets_to_model(self,s):
        try:
            soprano_stream = s.getElementById('Soprano').flat.notesAndRests
        except:
            return

        melody_offsets = [element.offset for element in soprano_stream]

        self.melody_offset_model = _update_markov(melody_offsets,self.melody_offset_model,self.melody_offset_order)

    