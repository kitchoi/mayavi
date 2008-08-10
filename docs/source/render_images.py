"""
Script to render the images for the Mayavi user guide.

This scipts requires image magic to be installed.

"""
# Author: Gael Varoquaux <gael dot varoquaux at normalesup dot org>
# Copyright (c) 2007, Enthought, Inc.
# License: BSD Style.


import os
from enthought.mayavi import mlab
from enthought.mayavi.scripts import mayavi2

from inspect import getmembers

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        'mayavi', 'images')

#############################################################################
def capture_image(func, filename):
    """ Runs a function doing some mayavi drawing and save the resulting
        scene to a file.
    """
    mlab.clf()
    func()
    if not filename[-4:] in ('.jpg', '.png'):
        filename = '%s.jpg' % filename
    mlab.savefig(filename , size=(400, 400) )
    os.system('convert %s -trim %s' % (filename, filename))


def illustrate_module(module, directory=IMAGE_DIR):
    """ Uses the test functions of the modules (discovery ala nose) to 
        create images for each function tested. 
    """
    for name, func in getmembers(module):
        if not callable(func) or not name[:4] in ('test', 'Test'):
            continue
        # LaTeX doesn't like '.' in filename (sucks), so we replace them.
        filename = directory + os.sep + module.__name__.replace('.', '_') \
                        + '_' + name[5:]
        capture_image(func, filename=filename)

#############################################################################
# Entry point
@mlab.show
def main():
    mlab.figure(bgcolor=(1, 1, 1), fgcolor=(0, 0, 0), size=(400, 400))
    illustrate_module(mlab)
    mayavi2.close()

if __name__ == '__main__':
    main()
