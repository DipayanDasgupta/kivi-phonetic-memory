"""Words the engine must never touch or learn from.

This is a pragmatic, plug-replaceable dictionary. In production Kivi this
would be the system lexicon; here it is a curated list of high-frequency
English words that ASR renders reliably. Rewriting any of them risks
corrupting ordinary text, so the engine refuses them at learn time and
treats them as "real-word homophone risk" at rewrite time.

Note that "kiwi" is deliberately present: it is a dictionary word (a
fruit), which is exactly why rewriting it requires supporting context.
"""

COMMON_WORDS = frozenset("""
a about above after again against all am an and any are aren't as at be
because been before being below between both but by can cannot could
couldn't did didn't do does doesn't doing don't down during each few for
from further had hadn't has hasn't have haven't having he her here hers
herself him himself his how i if in into is isn't it its itself just
let's me more most mustn't my myself no nor not of off on once only or
other ought our ours ourselves out over own same shan't she should
shouldn't so some such than that the their theirs them themselves then
there these they this those through to too under until up very was
wasn't we were weren't what when where which while who whom why with
won't would wouldn't you your yours yourself yourselves

ask calls call called email emails emailed mail message messages msg
ping pings pings send sends sent reply replies replied meet meeting
meetings meet invite invited invites review reviews reviewed check
checked make makes made take takes taken give gives gave get gets got

day days week weeks month months year years today tomorrow yesterday
morning afternoon evening night monday tuesday wednesday thursday
friday saturday sunday january february march april may june july
august september october november december time times hour hours

work works working team teams project projects service services app
apps product products company companies client clients customer
customers meeting notes note task tasks todo

good great bad nice new old big small long short high low first last
next best better worse same different easy hard

food eat eats lunch dinner breakfast snack fruit fruits vegetable
apple apples banana bananas mango oranges grape grapes kiwi melon
berry berries peach pear plum watermelon papaya guava litchi cherry
rice bread milk eggs sugar salt tea coffee water juice
""".split())