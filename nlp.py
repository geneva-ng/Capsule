import openai
from dotenv import load_dotenv
import os

load_dotenv()

# OPENAI SETUP
api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    raise ValueError("API key not found in .env file")
openai.api_key = api_key

# GENERATE NLP FROM GCAL EVENT LIST
def generate(input_string):

    '''
    This is the main generative text function that links to the OpenAI API;
    uses the model specified to generate a raw output sentence parsed from 
    a comma-separated list of events originally taken from Google Calendar event data. 
    '''

    try:
        
        #1. CONSTRUCT INPUT
        prompt = "Pretend this string is full of contents from a newspaper. Summarize the entire newspaper in an elegant tone in under 115 characters: " + input_string

        #2. SPECIFY OUTPUT LENGTH
        max_char_length = 126
        max_tokens = max_char_length // 4  # Rough estimate

        #3. GENERATE OUTPUT
        response = openai.completions.create(
          model="gpt-3.5-turbo-instruct",  # specify the model
          prompt=prompt,
          max_tokens=max_tokens
        )
        output_text = response.choices[0].text.strip()

        #4. TRUNCATE IF NEEDED
        if len(output_text) > max_char_length:
            output_text = output_text[:max_char_length]

        return output_text

    #5. CATCH ERRORS 
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def prepare(phrase):

    # FAIL BASED ON INCOMPLETE SENTENCE
    if '.' in phrase:
        sentences = phrase.split('.', 1)
        sentence = sentences[0] + '.'
    else:
        return ''

    # REMOVE QUOTES FROM BEGINNING 
    if sentence.startswith('"'):
        sentence = sentence[1:]
    
    # FAIL BASED ON FORMATTING
    if not sentence[0].isupper():   # first char is not a capital letter
        return ''
    
    if '\n' in sentence:   #newline in sentence
        return ''
    
    first_word = sentence.split()[0] if sentence.split() else ''    #first word must be more than 1 character long
    if len(first_word) <= 1:
        return ''
    
    if len(sentence) <= 30:    #sentence must be more than 100 char long
        return ''
    
    # FAIL BASED ON CONTENT
    words_to_check = ["newspaper", "news", "paper", "Newspaper", "News", "Paper"]
    for word in words_to_check:
        if word in sentence:
            return ''
    
    # IF PASSED ALL, RETURN SENTENCE
    return sentence
    
def process(input):

    phrase = generate(input)
    sentence = prepare(phrase)
    attempts = 0
    max_attempts = 20

    for attempt in range(max_attempts):
        attempts += 1
        phrase = generate(input)
        print(f"attempted phrase: {phrase}")
        sentence = prepare(phrase)

        if len(sentence) > 1:
            return sentence 
        
    return "...what moment do these songs bring you back to?"


