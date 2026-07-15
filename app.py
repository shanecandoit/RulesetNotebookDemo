

class Term:
    pass

class Const(Term):
    def __init__(self, value):
        self.value = value  # e.g., an integer or string literal

    def __repr__(self):
        return str(self.value)

    def __eq__(self, other):
        return isinstance(other, Const) and self.value == other.value

class Var(Term):
    def __init__(self, name):
        self.name = name  # e.g., 'a', 'b'

    def __repr__(self):
        return f"?{self.name}"

class Func(Term):
    def __init__(self, name, args):
        self.name = name      # e.g., 'add'
        self.args = list(args)

    def __repr__(self):
        return f"{self.name}({', '.join(map(str, self.args))})"


def match(pattern: Term, subject: Term, env=None) -> dict | None:
    """Matches a pattern against a subject term. Returns bindings {var_name: term}."""
    if env is None:
        env = {}

    # If the pattern is a variable, bind it
    if isinstance(pattern, Var):
        if pattern.name in env:
            # Linear pattern check: must match previous binding
            return env if env[pattern.name] == subject else None
        new_env = env.copy()
        new_env[pattern.name] = subject
        return new_env

    # If the pattern is a constant, it must match the subject exactly
    if isinstance(pattern, Const):
        if isinstance(subject, Const) and pattern.value == subject.value:
            return env
        return None

    # If the pattern is a function, names and arities must match
    if isinstance(pattern, Func):
        if not isinstance(subject, Func) or pattern.name != subject.name:
            return None
        if len(pattern.args) != len(subject.args):
            return None
        
        # Match all sub-arguments recursively
        current_env = env
        for p_arg, s_arg in zip(pattern.args, subject.args):
            current_env = match(p_arg, s_arg, current_env)
            if current_env is None:
                return None
        return current_env

    return None


def substitute(template: Term, env: dict) -> Term:
    """Replaces variables in a template term with their bound values from env."""
    if isinstance(template, Var):
        return env.get(template.name, template)
    if isinstance(template, Const):
        return template
    if isinstance(template, Func):
        # We also support basic arithmetic evaluation for terms like (a + 1)
        # to handle rules like add(a + 1, b - 1)
        if template.name in ('+', '-'):
            left = substitute(template.args[0], env)
            right = substitute(template.args[1], env)
            if isinstance(left, Const) and isinstance(right, Const):
                if template.name == '+':
                    return Const(left.value + right.value)
                elif template.name == '-':
                    return Const(left.value - right.value)
            return Func(template.name, [left, right])
            
        return Func(template.name, [substitute(arg, env) for arg in template.args])
    return template


class Rule:
    def __init__(self, lhs: Term, rhs: Term):
        self.lhs = lhs
        self.rhs = rhs

def rewrite_step(term: Term, rules: list[Rule]) -> tuple[Term, bool]:
    """Tries to apply a rewrite rule at the root of the term."""
    for rule in rules:
        env = match(rule.lhs, term)
        if env is not None:
            # Successfully matched! Construct the replacement
            return substitute(rule.rhs, env), True
    return term, False

def evaluate(term: Term, rules: list[Rule]) -> Term:
    """Innermost evaluation strategy: reduce children first, then apply rules."""
    if isinstance(term, Func):
        # 1. Recursively reduce all child arguments
        reduced_args = [evaluate(arg, rules) for arg in term.args]
        new_term = Func(term.name, list(reduced_args))
    else:
        new_term = term

    # 2. Try to rewrite the current node
    new_term, changed = rewrite_step(new_term, rules)
    
    # 3. If a rule matched, the new term might be further reducible
    if changed:
        return evaluate(new_term, rules)
        
    return new_term


# Helper to quickly write (a + 1) syntax trees
def add_expr(left, right):
    return Func("+", [left, right])

def sub_expr(left, right):
    return Func("-", [left, right])

# Define the rules
# Rule 1: add(a, 0) -> a
rule1 = Rule(
    lhs=Func("add", [Var("a"), Const(0)]),
    rhs=Var("a")
)

# Rule 2: add(a, b) -> add(a + 1, b - 1)
rule2 = Rule(
    lhs=Func("add", [Var("a"), Var("b")]),
    rhs=Func("add", [add_expr(Var("a"), Const(1)), sub_expr(Var("b"), Const(1))])
)

rules = [rule1, rule2]

# Let's compute: add(2, 3)
# It should rewrite:
# add(2, 3) -> add(3, 2) -> add(4, 1) -> add(5, 0) -> 5
# expr = Func("add", [Const(2), Const(3)])
# print("Input :", expr)

# result = evaluate(expr, rules)
# print("Output:", result)
