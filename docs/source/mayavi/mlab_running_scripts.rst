.. _running-mlab-scripts:

Running mlab scripts
---------------------

Mlab, like the rest of Mayavi, is an interactive application. If you are
not already in an interactive environment (see next paragraph), to
interact with the figures or the rest of the drawing elements, you need
to use the :func:`show` function. For instance, if you are writing a
script, you need to call :func:`show` each time you want to display one
or more figures and allow the user to interact with them.


.. _ipython-gui-setup-for-mlab:

Using mlab interactively
~~~~~~~~~~~~~~~~~~~~~~~~~

Using IPython_, mlab instructions can be run interactively, or in
scripts using IPython_'s ``%run`` command::

    In [1]: %run my_script

You should start IPython with the appropriate switches.

    * If PyFace version >= 5.0.0, the default ETS GUI toolkit is `Qt4`.
      You should start IPython with::

        $ ipython --gui=qt

    * If PyFace version < 5.0.0, the default ETS GUI toolkit is `wxPython`.
      You should start IPython with::

        $ ipython --gui=wx

In this environment, the plotting commands are interactive: they have an
immediate effect on the figure, alleviating the need to use the
:func:`show` function. 

Mlab can also be used interactively in the Python shell of the mayavi2
application, or in any interactive Python shell of Qt/wxPython-based
application (such as other Envisage-based applications, or SPE, Stani's
Python Editor).

.. note::
   
   The user may enforce one of the two GUI toolkits by setting
   the shell environment variable ``ETS_TOOLKIT``, for example,
   to use `wxPython` as the GUI toolkit::

         $ export ETS_TOOLKIT=wx
         $ ipython --gui=wx

    It should be noted that Mayavi depends on `ETS_TOOLKIT` and not
    the IPython `--gui` switch.  For example, in the following setup,
    Mayavi will use the `Qt4` toolkit::

         $ export ETS_TOOLKIT=qt4
         $ ipython --gui=wx             # inconsistent switch
         >>> from mayavi import mlab    # qt4 is still being used

    For IPython versions older than 1.0.0, you should check the IPython_
    documentation.

    Please note that, as of PyFace version 5.0, `Qt5` is not supported
    (see :ref:`known_bugs`).


Using together with Matplotlib's pylab
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to use Matplotlib's pylab with Mayavi's mlab in IPython, you
will need both the `--gui` and `--matplotlib` (previously `--pylab`)
switches in IPython, i.e.:

    * For GUI toolkit being `Qt` (default since PyFace 5.0.0):
        $ ipython --gui=qt --matplotlib

    * For GUI toolkit being `wxPython`
        $ ipython --gui=wx --matplotlib

For IPython versions older than 1.0.0, you should check the IPython_
documentation.

.. _IPython: http://ipython.scipy.org

.. topic:: Capturing mlab plots to integrate in pylab

    Starting from Mayavi version 3.4.0, the mlab :func:`screenshot` can
    be used to take a screenshot of the current figure, to integrate in a
    matplotlib plot.

In scripts
~~~~~~~~~~~~~~~~~

Mlab commands can be written to a file, to form a script. This script
can be loaded in the Mayavi application using the *File->Open file* menu
entry, and executed using the *File->Refresh code* menu entry or by
pressing ``Control-r``.  It can also be executed during the start of the
Mayavi application using the ``-x`` command line switch.

As mentioned above, when running outside of an interactive environment,
for instance with `python myscript.py`, you need to call the
:func:`show` function (as shown in the demo_ above) to pause your script
and have the user interact with the figure.

.. _demo:
    :ref:`mlab-demo`

You can also use :func:`show` to decorate a function, and have it run in
the event-loop, which gives you more flexibility::

 from mayavi import mlab
 from numpy import random
 
 @mlab.show
 def image():
    mlab.imshow(random.random((10, 10)))

With this decorator, each time the `image` function is called, `mlab`
makes sure an interactive environment is running before executing the
`image` function. If an interactive environment is not running, `mlab`
will start one and the image function will not return until it is closed.

..
   Local Variables:
   mode: rst
   indent-tabs-mode: nil
   sentence-end-double-space: t
   fill-column: 70
   End:

