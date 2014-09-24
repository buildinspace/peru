import asyncio


def stable_gather(*coros):
    '''asyncio.gather() starts tasks in a nondeterministic order (because it
    calls set() on its arguments). Start the list of tasks in order, and pass
    the resulting futures to gather().'''
    assert len(coros) == len(set(coros)), 'no duplicates'
    futures = [asyncio.async(coro) for coro in coros]
    return asyncio.gather(*futures)
