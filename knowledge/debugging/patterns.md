# Common bug patterns

## Mutable default argument
Label: mutable default argument
Pattern: mutable_default
Tags: mutable default argument list dict shared between calls state persists earlier call remembered
A default value is created once, when the function is defined, and every call shares it. A list or dictionary default keeps changes made by earlier calls.
Hint1: Look at `{expr}`: expected {expected}, got {actual}. Something from an earlier call is still there. Where could a value be stored between calls?
Hint2: The default value at {where} is created once, when the function is defined, and every call shares it. A list or dictionary used as a default keeps its changes.
Hint3: Use None as the default value. Inside the function, create a new list only when the argument is None, then work with that list.
Lesson: Default values are evaluated once at definition time. Use None as the default and build a fresh object inside the function.

## Changing a list while looping over it
Label: changing a list while looping over it
Pattern: modify_while_iterating
Tags: modify list while iterating loop remove skipped items delete same collection copy
Removing items from a list during a loop shifts the remaining items, so the loop skips the item that moves into the current position.
Hint1: Test `{expr}`: expected {expected}, got {actual}. Some items were skipped. What happens to the positions of the other items when you remove one during a loop?
Hint2: At {where} you change the same list the loop is reading. After a removal, the next item moves into the current position and the loop steps past it.
Hint3: Loop over a copy of the list, or build a new list that holds only the items to keep. If the original list must change, remove from it while looping over the copy.
Lesson: Do not change a collection while looping over it. Loop over a copy or build a new collection.

## Late-binding closure
Label: late-binding closure
Pattern: late_binding
Tags: closure lambda loop variable late binding functions created in a loop all same result captured
A function that uses a variable from outside itself reads that variable when it is called, not when it is created, so functions created in a loop all see the final value.
Hint1: Test `{expr}`: expected {expected}, got {actual}. The functions all behave alike. When does a function look up a variable that lives outside of it?
Hint2: The function created at {where} reads the loop variable when it is called, not when it is created. After the loop ends, every function sees the final value.
Hint3: Capture the current value when each function is created. One way is a default parameter that copies the loop variable. Another is a helper function that takes the value and returns the new function.
Lesson: Closures look up outside variables at call time. Bind the value at creation time with a default parameter or a helper function.

## Off-by-one error
Label: off-by-one error
Pattern: off_by_one
Tags: off by one range stop value loop one too few too many boundary last item slice
A loop or slice runs one time too few or too many, usually because the stop value is wrong.
Hint1: Test `{expr}`: expected {expected}, got {actual}. Count how many times your loop runs for this input. Is that the number you need?
Hint2: The range or slice at {where} stops one item early. range(n) produces n numbers, starting at 0, and the last one is n - 1.
Hint3: Compare the number of loop passes with the number of items you need. Fix the stop value so the last needed item is included, then recheck the edge cases: zero items, one item, and n larger than the list.
Lesson: range(n) runs n times and ends at n - 1. Check the first and last pass for every loop.

## Inverted condition or swapped result
Label: inverted condition or swapped result
Pattern: inverted_condition
Tags: inverted condition swapped result opposite reversed comparison branch wrong direction higher lower
A comparison is reversed, or two results are swapped, so the answer is the opposite of the expected one.
Hint1: Test `{expr}`: expected {expected}, got {actual}. The answer is the opposite of what is needed. Which branch of {function} handles this input?
Hint2: In {function}, a comparison or a returned value is reversed. Check each branch against the description: which input reaches it, and does it return the matching result?
Hint3: Write each branch of the description as a sentence, for example "if the temperature is above the limit, return Too Hot". Then make the code say the same thing, by swapping the comparison or the returned value.
Lesson: Check each branch against the specification, one input at a time.

## Letter case
Label: letter case
Pattern: case_sensitivity
Tags: case sensitivity uppercase lowercase letters compare characters upper lower capital
Python treats uppercase and lowercase letters as different characters, so a comparison written for one case misses the other.
Hint1: Test `{expr}`: expected {expected}, got {actual}. Compare this input with the inputs that pass. What is different about the letters?
Hint2: {function} treats uppercase and lowercase letters as different characters. In Python, "A" is not equal to "a".
Hint3: Convert each character, or the whole text, to one case before comparing. Strings have built-in methods for that.
Lesson: Normalize case before comparing text.

## Wrong result
Label: wrong result
Pattern: wrong_value
Tags: wrong result value differs expected actual logic constant condition hand trace
No specific pattern matched. The results differ from the expected values, so the best step is to compare the code with a hand calculation.
Hint1: {failed} of {total} tests fail. Start with `{expr}`: expected {expected}, got {actual}. Work through that input by hand. Where does your code first differ from your hand result?
Hint2: The failing test calls {function}. Add a temporary print inside it for this input and compare each step with your hand calculation. The first step that differs is the bug.
Hint3: Reread the exercise description for {function} one sentence at a time and check that your code does each thing in it. Look for a constant, a comparison, or a condition that does not match the sentence.
Lesson: Trace a failing input by hand and find the first step where the code and your expectation differ.
