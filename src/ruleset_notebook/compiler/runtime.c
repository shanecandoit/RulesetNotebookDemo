#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Term {
    struct Term *next_allocation;
    const char *symbol; /* NULL for an integer. */
    int64_t value;
    size_t arity;
    size_t depth;
    const struct Term *children[];
} Term;

typedef struct {
    Term *allocations;
    const char *error;
} Evaluation;

typedef enum {
    NO_MATCH,
    REWRITTEN,
    REWRITE_ERROR
} RewriteStatus;

typedef RewriteStatus (*RuleFunction)(Evaluation *, const Term *, const Term **);

typedef struct {
    const char *trace_name;
    RuleFunction apply;
} RuleEntry;

typedef struct {
    const char *kind;
    const char *trace_name;
    size_t position_length;
    const Term *term;
} Rewrite;

static void allocation_failed(void)
{
    fputs("Term evaluation ran out of memory.\n", stderr);
    exit(EXIT_FAILURE);
}

static void *checked_allocate(size_t size)
{
    void *memory = malloc(size);
    if (memory == NULL) {
        allocation_failed();
    }
    return memory;
}

static Term *allocate_term(Evaluation *evaluation, const char *symbol, size_t arity)
{
    if (arity > (SIZE_MAX - sizeof(Term)) / sizeof(const Term *)) {
        allocation_failed();
    }
    Term *term = checked_allocate(sizeof(Term) + arity * sizeof(term->children[0]));
    term->next_allocation = evaluation->allocations;
    term->symbol = symbol;
    term->value = 0;
    term->arity = arity;
    term->depth = 1;
    evaluation->allocations = term;
    return term;
}

static void release_terms(Evaluation *evaluation)
{
    while (evaluation->allocations != NULL) {
        Term *term = evaluation->allocations;
        evaluation->allocations = term->next_allocation;
        free(term);
    }
}

static const Term *make_integer(Evaluation *evaluation, int64_t value)
{
    Term *term = allocate_term(evaluation, NULL, 0);
    term->value = value;
    return term;
}

static void set_child(Term *parent, size_t index, const Term *child)
{
    parent->children[index] = child;
    if (child->depth >= parent->depth) {
        parent->depth = child->depth + 1;
    }
}

static const Term *make_application(
    Evaluation *evaluation, const char *symbol, size_t arity, const Term *const *children)
{
    Term *term = allocate_term(evaluation, symbol, arity);
    for (size_t index = 0; index < arity; ++index) {
        set_child(term, index, children[index]);
    }
    return term;
}

static const Term *replace_child(
    Evaluation *evaluation, const Term *term, size_t index, const Term *replacement)
{
    Term *copy = allocate_term(evaluation, term->symbol, term->arity);
    for (size_t child = 0; child < term->arity; ++child) {
        set_child(copy, child, child == index ? replacement : term->children[child]);
    }
    return copy;
}

static bool is_integer(const Term *term)
{
    return term->symbol == NULL;
}

static inline bool is_application(const Term *term, const char *symbol, size_t arity)
{
    return !is_integer(term) && term->arity == arity && strcmp(term->symbol, symbol) == 0;
}

static inline bool terms_equal(const Term *left, const Term *right)
{
    if (left == right) {
        return true;
    }
    if (is_integer(left)) {
        return is_integer(right) && left->value == right->value;
    }
    if (!is_application(right, left->symbol, left->arity)) {
        return false;
    }
    for (size_t index = 0; index < left->arity; ++index) {
        if (!terms_equal(left->children[index], right->children[index])) {
            return false;
        }
    }
    return true;
}

typedef enum { ADD, SUBTRACT, MULTIPLY, DIVIDE } Operation;

typedef struct {
    const char *symbol;
    const char *trace_name;
    size_t arity;
    Operation operation;
} Builtin;

static const Builtin builtins[] = {
    {"inc", "\"inc\"", 1, ADD},
    {"dec", "\"dec\"", 1, SUBTRACT},
    {"add", "\"add\"", 2, ADD},
    {"+", "\"+\"", 2, ADD},
    {"sub", "\"sub\"", 2, SUBTRACT},
    {"-", "\"-\"", 2, SUBTRACT},
    {"mul", "\"mul\"", 2, MULTIPLY},
    {"div", "\"div\"", 2, DIVIDE},
};

static bool multiply_overflows(int64_t left, int64_t right)
{
    if (left > 0) {
        return (right > 0 && left > INT64_MAX / right)
            || (right < 0 && right < INT64_MIN / left);
    }
    if (left < 0) {
        return (right > 0 && left < INT64_MIN / right)
            || (right < 0 && left < INT64_MAX / right);
    }
    return false;
}

static const char *calculate(
    Operation operation, int64_t left, int64_t right, int64_t *result)
{
    switch (operation) {
    case ADD:
        if ((right > 0 && left > INT64_MAX - right)
            || (right < 0 && left < INT64_MIN - right)) {
            return "integer-overflow";
        }
        *result = left + right;
        return NULL;
    case SUBTRACT:
        if ((right > 0 && left < INT64_MIN + right)
            || (right < 0 && left > INT64_MAX + right)) {
            return "integer-overflow";
        }
        *result = left - right;
        return NULL;
    case MULTIPLY:
        if (multiply_overflows(left, right)) {
            return "integer-overflow";
        }
        *result = left * right;
        return NULL;
    case DIVIDE:
        return right == 0 ? "division-by-zero" : "unsupported-builtin-division";
    }
    return "unknown-operation";
}

static RewriteStatus try_builtin(Evaluation *evaluation, const Term *term, Rewrite *rewrite)
{
    if (is_integer(term)) {
        return NO_MATCH;
    }
    for (size_t index = 0; index < sizeof(builtins) / sizeof(builtins[0]); ++index) {
        const Builtin *builtin = &builtins[index];
        if (strcmp(term->symbol, builtin->symbol) != 0) {
            continue;
        }
        if (term->arity != builtin->arity || !is_integer(term->children[0])
            || (builtin->arity == 2 && !is_integer(term->children[1]))) {
            evaluation->error = "invalid-operand";
            return REWRITE_ERROR;
        }
        int64_t left = term->children[0]->value;
        int64_t right = builtin->arity == 1 ? 1 : term->children[1]->value;
        int64_t result = 0;
        evaluation->error = calculate(builtin->operation, left, right, &result);
        if (evaluation->error != NULL) {
            return REWRITE_ERROR;
        }
        rewrite->term = make_integer(evaluation, result);
        rewrite->kind = "built-in";
        rewrite->trace_name = builtin->trace_name;
        return REWRITTEN;
    }
    return NO_MATCH;
}

static RewriteStatus try_at_position(
    Evaluation *evaluation, const Term *term, const RuleEntry *rules, size_t rule_count,
    Rewrite *rewrite)
{
    for (size_t index = 0; index < rule_count; ++index) {
        RewriteStatus status = rules[index].apply(evaluation, term, &rewrite->term);
        if (status == REWRITTEN) {
            rewrite->kind = "rule";
            rewrite->trace_name = rules[index].trace_name;
        }
        if (status != NO_MATCH) {
            return status;
        }
    }
    return try_builtin(evaluation, term, rewrite);
}

static RewriteStatus try_innermost(
    Evaluation *evaluation, const Term *term, const RuleEntry *rules, size_t rule_count,
    size_t *position, size_t position_length, Rewrite *rewrite)
{
    for (size_t index = 0; index < term->arity; ++index) {
        position[position_length] = index;
        RewriteStatus status = try_innermost(evaluation, term->children[index],
            rules, rule_count, position, position_length + 1, rewrite);
        if (status == REWRITTEN) {
            rewrite->term = replace_child(evaluation, term, index, rewrite->term);
        }
        if (status != NO_MATCH) {
            return status;
        }
    }
    rewrite->position_length = position_length;
    return try_at_position(evaluation, term, rules, rule_count, rewrite);
}

static void print_term(const Term *term)
{
    if (is_integer(term)) {
        printf("%" PRId64, term->value);
        return;
    }
    printf("%s(", term->symbol);
    for (size_t index = 0; index < term->arity; ++index) {
        if (index != 0) {
            fputs(", ", stdout);
        }
        print_term(term->children[index]);
    }
    putchar(')');
}

static void print_step(size_t step, const Rewrite *rewrite, const size_t *position)
{
    printf("STEP %zu ", step);
    print_term(rewrite->term);
    printf(" KIND %s POSITION ", rewrite->kind);
    if (rewrite->position_length == 0) {
        fputs("root", stdout);
    }
    for (size_t index = 0; index < rewrite->position_length; ++index) {
        printf("%s%zu", index == 0 ? "" : ".", position[index]);
    }
    printf(" NAME %s\n", rewrite->trace_name);
}

static void run_input(
    Evaluation *evaluation, size_t input_index, size_t source_line, const Term *input,
    const RuleEntry *rules, size_t rule_count, size_t max_steps, size_t max_depth)
{
    printf("INPUT %zu LINE %zu TERM ", input_index, source_line);
    print_term(input);
    fputs("\nSTEP 0 ", stdout);
    print_term(input);
    putchar('\n');

    const Term *current = input;
    const char *status = "depth limit";
    if (input->depth <= max_depth) {
        if (max_depth > SIZE_MAX / sizeof(size_t)) {
            allocation_failed();
        }
        size_t *position = checked_allocate(max_depth * sizeof(*position));
        status = "step limit";
        for (size_t step = 0; step < max_steps; ++step) {
            Rewrite rewrite = {0};
            RewriteStatus attempt =
                try_innermost(evaluation, current, rules, rule_count, position, 0, &rewrite);
            if (attempt == NO_MATCH) {
                status = "normal form";
                break;
            }
            if (attempt == REWRITE_ERROR) {
                status = "runtime error";
                break;
            }
            if (rewrite.term->depth > max_depth) {
                status = "depth limit";
                break;
            }
            current = rewrite.term;
            print_step(step + 1, &rewrite, position);
        }
        free(position);
    }

    fputs("RESULT ", stdout);
    print_term(current);
    printf("\nSTATUS %s\n", status);
    if (evaluation->error != NULL) {
        printf("ERROR %s\n", evaluation->error);
    }
}
