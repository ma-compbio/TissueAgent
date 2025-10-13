from queue import Queue, Empty
from threading import Thread
from agents.agent_registry.coding_agent.model import create_coding_agent

def drain(q):
    while True:
        try:
            msg = q.get(timeout=0.1)
            if msg is None:
                break
            print(msg, flush=True)
        except Empty:
            continue

def main():
    q = Queue()
    tool = create_coding_agent(q)
    t = Thread(target=drain, args=(q,), daemon=True)
    t.start()
    print("Type a prompt to interact with the agent. Type 'exit' to quit.")
    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if prompt.lower() in {"exit", "quit"}:
            break
        if not prompt:
            continue
        result = tool.invoke(prompt)
        print(f"\nAgent:\n{result}\n", flush=True)
    q.put(None)

if __name__ == "__main__":
    main()


# Load the default slide-seq dataset from Squidpy and generate a spatial scatterplot of it. Store the resulting figure in /Users/dustinm/Projects/research/ma-lab/TissueAgent/data/.