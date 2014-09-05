import os


def makedirs(path):
    '''os.makedirs() has an exist_ok param, but it still throws errors when the
    path exists with non-default permissions. This isn't fixed until 3.4.'''
    if not os.path.exists(path):
        os.makedirs(path)
