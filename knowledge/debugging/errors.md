# Errors that stop the code

## Syntax error
Label: syntax error
Pattern: syntax_error
Tags: syntax error invalid code colon bracket quote indentation cannot read
Python could not read the code, so no test ran. The message and line number point near the problem.
Hint1: Python could not read your code, so no test ran. Read the error message. It points near {where}.
Hint2: Check {where} and the line before it for a missing colon, an unclosed bracket or quote, or an indentation mistake. The message was: {error}.
Hint3: Fix the reported line first, then run again. Syntax errors are often one line above the line Python reports, in an unclosed bracket or a missing colon.
Lesson: Read the first error message and fix only that one before running again.

## Blocked code
Label: blocked code
Pattern: blocked_code
Tags: blocked import not allowed restricted file system network input
The exercise runner refuses imports and calls that touch files, the network, or the keyboard.
Hint1: The checker blocked something in your code: {error}.
Hint2: Exercises run in a restricted runner. Remove the blocked item near {where} and solve the exercise with plain Python.
Hint3: Every exercise can be solved with built-in types and loops. Remove the blocked import or call and use plain Python instead.
Lesson: Keep exercise solutions free of file, network, and keyboard access.

## Code that never finishes
Label: infinite loop
Pattern: infinite_loop
Tags: infinite loop timeout never ends too long while loop condition
The code ran past the time limit, which usually means a loop never reaches its stop condition.
Hint1: Your code ran too long and was stopped. Which loop might never reach its end condition?
Hint2: A loop probably does not change the value its condition checks. Trace each loop by hand with a small input.
Hint3: For every loop, write down what changes on each pass and what makes it stop. If nothing moves toward stopping, add the missing update.
Lesson: Every loop needs something that changes toward its stop condition.

## Error before the tests run
Label: error at load time
Pattern: load_error
Tags: load error exception before tests import name undefined top level crash
The file raised an error while loading, so no test could call the function.
Hint1: Your file fails before any test can run. The error was: {error}.
Hint2: The error comes from code that runs when the file loads, near {where}. Check names, spelling, and anything written outside a function.
Hint3: Comment out everything outside the function definitions and add code back one piece at a time until the error returns.
Lesson: Code outside functions runs as soon as the file loads, so errors there stop every test.

## Error inside a test
Label: runtime error
Pattern: runtime_error
Tags: runtime error exception crashed raised index type name value error traceback
A test crashed with an exception instead of returning a value.
Hint1: A test crashed instead of returning a value. Walk through `{expr}` by hand. Where could it raise an error?
Hint2: {error} was raised at {where} while running `{expr}`. What value did that line expect, and what did it get?
Hint3: Check the types and sizes of the values at {where}. Common causes are indexing past the end, using a name before it is set, or mixing types. Guard or correct that step.
Lesson: Read the exception type and line number first. They usually name the exact problem.
