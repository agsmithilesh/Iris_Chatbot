import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

SYSTEM_PROMPT = """You are a helpful file assistant with access to the following tools:

- read_file(path: str): reads a file from disk and returns its content
- write_file(path: str, content: str): writes content to a file on disk

When you need to use a tool, emit EXACTLY this format and nothing else after it:

<tool_call>
{"name": "TOOL_NAME", "arguments": {"arg1": "value1"}}
</tool_call>

After you receive the tool result in a <tool_response> block, continue your response
normally. Do not emit a tool_call and prose in the same turn. Pick one or the other.
"""

def read_file(path):
    try:
        file = open(path,"r")
        data = file.read()
        return {"content":data, "path" : path}
    except:
        return {"error": "The file can't be read"}

def write_file(path , content):
    try:
        file = open(path,"w")
        data = file.write(content)
        return {"success":True, "path":path, "Bytes":len(content)}
    except:
        return{"error": "Unable to write to the file"}

def parse_tool_call(response_text):
    if not response_text:
        return None
    pattern = r"<tool_call>(.*?)</tool_call>"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        extracted = match.group(1)
        tool = json.loads(extracted)
        name = tool["name"]
        arg = tool["arguments"]
        return name,arg
    else:
        return None

def strip_tool_call(response_text):
    return(re.sub(r"<tool_call>.*?</tool_call>","", response_text, flags=re.DOTALL))

TOOL_REGISTRY = {
    "read_file": read_file,
    "write_file": write_file,}

def dispatch(name,arg):
   if name=="read_file":
        tool_run = TOOL_REGISTRY["read_file"](arg["path"])
        resp = json.dumps(tool_run)
        return(resp)

   elif(name == "write_file"):
       tool_run = TOOL_REGISTRY["write_file"](arg["path"],arg["content"])
       resp = json.dumps(tool_run)
       return(resp)
   else:
       a = ({"error": f"Unknown tool: {name}"})
       b = json.dumps(a)
       return b

MAX_ITERATIONS = 6

def run_agent(user_message):
    messages = [{"role":"system", "content":SYSTEM_PROMPT},{"role":"user", "content": user_message}]

    for i in range(MAX_ITERATIONS):
        response = client.chat.completions.create(model="openrouter/owl-alpha", messages=messages)
        reply = response.choices[0].message.content
        if reply is None:
            reply = "no reply"
        messages.append({"role":"assistant", "content":reply})
        simplified_reply = strip_tool_call(reply)
        if(simplified_reply!=""):
            print(f"AI: {simplified_reply}")
            print("="*40)

        tool_call = parse_tool_call(reply)

        if tool_call:
            name , arg = tool_call
            tool_response = dispatch(name,arg)
            messages.append({"role":"user", "content":f"<tool_response>\n{tool_response}\n</tool_response>"})
        else:
            break

        if(i==MAX_ITERATIONS):
            print (f"[Agent stopped after {MAX_ITERATIONS} iterations]")

if __name__ == "__main__":
    with open("build1_sample.txt", "w") as f:
        f.write("IIT Delhi was established in 1961. It is one of the premier engineering institutions in India.\n")
        f.write("The campus spans 325 acres in Hauz Khas, New Delhi.\n")

    test_queries = [
        "Read build1_sample.txt and summarise what it says.",
        "Read build1_sample.txt and write a one-sentence version of its content to summary.txt.",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        print(f"{'='*60}")
        result = run_agent(query)