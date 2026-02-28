from toygres.constants import MATRIX_GREEN, RESET
import os


class TokenCosts:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0

    def add_tokens(self, input_tokens: int, output_tokens: int):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def get_total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def print_costs(self):

        print(f"\n{MATRIX_GREEN}--- Session Token Usage ---{RESET}")
        print(f"{MATRIX_GREEN}Input Tokens: {self.input_tokens}{RESET}")
        print(f"{MATRIX_GREEN}Output Tokens: {self.output_tokens}{RESET}")
        print(f"{MATRIX_GREEN}Total Tokens: {self.get_total_tokens()}{RESET}")

        in_cost_env = os.getenv("INPUT_COST_PER_MILLION_TOKEN")
        out_cost_env = os.getenv("OUTPUT_COST_PER_MILLION_TOKEN")

        if in_cost_env and out_cost_env:
            try:
                in_cost = float(in_cost_env)
                out_cost = float(out_cost_env)
                total_cost = (self.input_tokens / 1_000_000) * in_cost + (
                    self.output_tokens / 1_000_000
                ) * out_cost
                print(f"{MATRIX_GREEN}Estimated Cost: ${total_cost:.6f}{RESET}")
            except ValueError:
                pass

        print(f"{MATRIX_GREEN}---------------------------{RESET}\n")


# Global instance to track costs across the session
session_costs = TokenCosts()
