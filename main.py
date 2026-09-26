"""Entry point: pick a role, then chat with the Shopping Agent."""

from agent import ShoppingAgent


def main() -> None:
    print("=" * 60)
    print("SIMPLE SAFE SHOPPING AGENT")
    print("=" * 60)

    role = input("Login as role [customer/admin] (default customer): ").strip().lower() or "customer"
    if role not in {"customer", "admin"}:
        print(f"Unknown role '{role}', defaulting to customer.")
        role = "customer"

    agent = ShoppingAgent(user_role=role)
    print(f"\nLogged in as: {role}")
    print("Try: 'Find the cheapest laptop in stock', 'Buy 1 of product 2', 'Delete product 4'")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        print("\nFINAL ANSWER:", agent.run(user_input))
        print()


if __name__ == "__main__":
    main()