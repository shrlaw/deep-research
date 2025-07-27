import streamlit as st
import os
import json
import itertools
from openai import OpenAI

# --- Modular Functions ---
def get_openai_client(api_key):
    os.environ['OPENAI_API_KEY'] = api_key
    return OpenAI()

# Ask for OpenAI API key
st.title("Deep Research Clone")
api_key = st.text_input("Enter your OpenAI API key:", type="password")

if api_key:
    client = get_openai_client(api_key)
    MODEL = "gpt-4o"
    MODEL_MINI = "gpt-3.5-turbo"
    TOOLS = [{ "type": "web_search" }]
    developer_message = """
You are an expert Deep Researcher.
You provide complete and in depth research to the user.
"""

    # Step 1: Topic input
    topic = st.text_input("Please enter the research topic:")
    if topic:
        # Step 2: Clarifying questions
        prompt_to_clarify = f"""
Ask 5 numbered clarifying question to the user about the topic: {topic}.
The goal of the questions is to understand the intended purpose of the research.
Reply only with the questions
"""
        if st.button("Generate clarifying questions") or 'clarify' in st.session_state:
            if 'clarify' not in st.session_state:
                clarify = client.responses.create(
                    model=MODEL_MINI,
                    input=prompt_to_clarify,
                    instructions=developer_message
                )
                st.session_state['clarify'] = clarify
            else:
                clarify = st.session_state['clarify']
            questions = clarify.output[0].content[0].text.split("\n")
            st.write("### Clarifying Questions:")
            answers = []
            for i, question in enumerate(questions):
                answer = st.text_input(f"{question}", key=f"answer_{i}")
                answers.append(answer)
            if all(answers):
                # Step 3: Generate goal and queries
                prompt_goals = f"""
Using the user answers {answers} to que questions {questions}, write a goal sentence and 5 web search queries for the research about {topic}
Output: A json list of the goal and the 5 web search queries that will reach it.
Format: {{\"goal\": \"...\", \"queries\": [\"q1\", ....]}}
"""
                if st.button("Generate research plan") or 'plan' in st.session_state:
                    if 'plan' not in st.session_state:
                        goal_and_queries = client.responses.create(
                            model=MODEL,
                            input=prompt_goals,
                            previous_response_id=clarify.id,
                            instructions=developer_message
                        )
                        st.session_state['plan'] = goal_and_queries
                    else:
                        goal_and_queries = st.session_state['plan']
                    plan = json.loads(goal_and_queries.output[0].content[0].text)
                    goal = plan["goal"]
                    queries = plan["queries"]
                    st.write(f"**Research Goal:** {goal}")
                    st.write("**Web Search Queries:**")
                    for q in queries:
                        st.write(f"- {q}")

                    # Step 4: Web search and collection
                    if st.button("Run research") or 'collected' in st.session_state:
                        def run_search(q):
                            web_search = client.responses.create(
                                model=MODEL,
                                input=f"search: {q}",
                                instructions=developer_message,
                                tools=TOOLS
                            )
                            return {"query": q,
                                    "resp_id": web_search.output[1].id,
                                    "research_output": web_search.output[1].content[0].text}
                        def evaluate(collected):
                            review = client.responses.create(
                                model=MODEL,
                                input=[
                                    {"role": "developer", "content": f"Research goal: {goal}"},
                                    {"role": "assistant", "content": json.dumps(collected)},
                                    {"role": "user", "content": "Does this information will fully satisfy the goal? Answer Yes or No only."}
                                ],
                                instructions=developer_message
                            )
                            return "yes" in review.output[0].content[0].text.lower()
                        collected = []
                        queries_to_run = queries
                        for _ in itertools.count():
                            for q in queries_to_run:
                                collected.append(run_search(q))
                            if evaluate(collected):
                                break
                            more_searches = client.responses.create(
                                model=MODEL,
                                input=[
                                    {"role": "assistant", "content": f"Current data: {json.dumps(collected)}"},
                                    {"role": "user", "content": f"This has not met the goal: {goal}. Write 5 other web searchs to achieve the goal"}
                                ],
                                instructions=developer_message,
                                previous_response_id=goal_and_queries.id
                            )
                            queries_to_run = json.loads(more_searches.output[0].content[0].text)
                        st.session_state['collected'] = collected
                        st.success("Research complete!")
                        # Step 5: Final report
                        report = client.responses.create(
                            model=MODEL,
                            input=[
                                {"role": "developer", "content": (f"Write a complete and detailed report about research goal: {goal}"
                                                                "Cite Sources inline using [n] and append a reference"
                                                                "list mapping [n] to url")},
                                {"role": "assistant", "content": json.dumps(collected)}],
                            instructions=developer_message
                        )
                        st.markdown("## Final Report")
                        st.markdown(report.output[0].content[0].text) 