import os
import json
import pandas as pd

from dotenv import load_dotenv
from google import genai
from google.genai import types


# ==================================================
# 1. Load API key
# ==================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")


# ==================================================
# 2. Connect to Gemini
# ==================================================

client = genai.Client(
    api_key=api_key
)


# ==================================================
# 3. Load risk data
# ==================================================

FILE_NAME = r"C:\FG\Market Risk AI\risk_data.csv"


def load_risk_data():

    data = pd.read_csv(FILE_NAME)

    previous = data.iloc[-2]
    current = data.iloc[-1]

    return previous, current


# ==================================================
# 4. Risk analysis functions
# ==================================================

def get_var_analysis():

    previous, current = load_risk_data()

    var_change = (
        current["var"]
        - previous["var"]
    )

    var_change_pct = (
        var_change
        / previous["var"]
    ) * 100

    return {
        "previous_var": float(previous["var"]),
        "current_var": float(current["var"]),
        "change": float(var_change),
        "change_pct": float(var_change_pct)
    }


def get_risk_factor_breakdown():

    previous, current = load_risk_data()

    risk_factors = {
        "EUR/USD": "EUR_USD",
        "USD/JPY": "USD_JPY",
        "Equity": "Equity",
        "Rates": "Rates"
    }

    results = {}

    for name, column in risk_factors.items():

        yesterday = previous[column]
        today = current[column]

        results[name] = {
            "previous": float(yesterday),
            "current": float(today),
            "change": float(
                today - yesterday
            )
        }

    return results


def get_limit_utilisation():

    previous, current = load_risk_data()

    utilisation = (
        current["var"]
        / current["var_limit"]
    ) * 100

    return {
        "current_var": float(current["var"]),
        "var_limit": float(
            current["var_limit"]
        ),
        "utilisation_pct": float(
            utilisation
        )
    }


# ==================================================
# 5. Define Gemini tools
# ==================================================

tools = [
    types.Tool(
        function_declarations=[

            types.FunctionDeclaration(
                name="get_var_analysis",
                description=(
                    "Calculate the change in "
                    "market VaR between the "
                    "previous and current day."
                ),
            ),

            types.FunctionDeclaration(
                name="get_risk_factor_breakdown",
                description=(
                    "Calculate changes in "
                    "major market risk factors "
                    "including EUR/USD, USD/JPY, "
                    "Equity and Rates."
                ),
            ),

            types.FunctionDeclaration(
                name="get_limit_utilisation",
                description=(
                    "Calculate current VaR "
                    "limit utilisation."
                ),
            )
        ]
    )
]


# ==================================================
# 6. Execute requested tool
# ==================================================

def execute_tool(function_name):

    if function_name == "get_var_analysis":

        return get_var_analysis()

    elif function_name == "get_risk_factor_breakdown":

        return get_risk_factor_breakdown()

    elif function_name == "get_limit_utilisation":

        return get_limit_utilisation()

    else:

        return {
            "error": "Unknown function"
        }


# ==================================================
# 7. Ask Gemini
# ==================================================

def ask_gemini(question):

    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            tools=tools
        )
    )

    response = chat.send_message(question)

    # ----------------------------------------------
    # Check whether Gemini wants to call a tool
    # ----------------------------------------------

    if response.function_calls:

        for function_call in response.function_calls:

            function_name = function_call.name

            print(
                f"\n[AI is calling: "
                f"{function_name}]"
            )

            result = execute_tool(
                function_name
            )

            # Send tool result back to Gemini
            response = chat.send_message(
                types.Part.from_function_response(
                    name=function_name,
                    response={
                        "result": result
                    }
                )
            )

    return response.text


# ==================================================
# 8. Chat interface
# ==================================================

print()
print("==============================")
print("     MARKET RISK AI ASSISTANT")
print("==============================")
print()
print("Risk engine ready.")
print("Ask me a market-risk question.")
print("Type 'exit' to stop.")
print()

while True:

    question = input("You: ")

    if question.lower() == "exit":

        print("Assistant: Goodbye.")
        break

    answer = ask_gemini(question)

    print()
    print("Assistant:")
    print(answer)
    print()