import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(base_url="https://openrouter.ai/api/v1",api_key=os.environ["OPENROUTER_API_KEY"],)

def run_chatbot():
    max_turns = 5
    curr_turns = 0

    messages = [{"role": "system", "content": "You are IRIS, a very famous detective. You are also very witty and sarcastic. You have a great sense of humor and you love to make jokes. You remember key details about the conversation but answer in a concise manner. You are also very good at summarizing the conversation when needed."}]
    print("Hi i am IRIS, your detective assistant. How can I help you today?")
    print("==" * 25)
    
    while True:

        if(len(messages)>=max_turns*2+1):
            print("==" * 25)
            messages.append({"role":"system","content":"Summarize the key points and also keep your response simple."})
            response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=messages)
            reply = response.choices[0].message.content
            messages.append({"role": "assistant", "content": reply})
            del messages[1:len(messages)-2]
            print(f"{reply}")
            print("==" * 25)

        if(curr_turns<=max_turns):
            percent = (curr_turns / max_turns) * 100
            if(percent >= 60):
                print(f"WARNING: YOU HAVE USED {percent}% OF YOUR TURNS. PLEASE CONSIDER STARTING A NEW CONVERSATION OTHERWISE THE MODEL MAY NOT BE ABLE TO RESPOND PROPERLY.")

        # Get user input
        user_input = input("You: ")
        
        # Check if user wants to quit
        if user_input.lower() in ["exit", "quit"]:
            print("GOODBYE AND GOOD LUCK WITH YOUR CASES!")
            break
        
        # Add user message to history
        messages.append({"role": "user", "content": user_input})

        # Send full history to AI
        response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=messages)

        # Tokens tracking
        total = response.usage.total_tokens

        # Get AI reply
        reply = response.choices[0].message.content
        
        # Add AI reply to history
        messages.append({"role": "assistant", "content": reply})

        # Print AI reply
        print(f"AI: {reply}")
        curr_turns += 1
        print(f"Tokens used - Total: {total}")
        print("-" * 40)

# Run it!
run_chatbot()