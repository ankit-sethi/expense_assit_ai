from ai.query_router import route_query


def main():

    print("=== Personal AI Assistant CLI ===")
    print("Type 'exit' to quit\n")

    while True:

        user_input = input("You: ")

        if user_input.lower() == "exit":
            break

        response = route_query(user_input)

        print("\nAssistant:")
        print(response)
        print("-" * 40)


if __name__ == "__main__":
    main()
