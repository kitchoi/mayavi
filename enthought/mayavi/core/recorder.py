"""
Code to support recording to a runnable Python script.

TODO:
    - Support for dictionaries?
"""
# Author: Prabhu Ramachandran <prabhu@aero.iitb.ac.in>
# Copyright (c) 2008, Enthought, Inc.
# License: BSD Style.

import warnings
import types
import __builtin__

from enthought.traits.api import (HasTraits, List, Str, Code, Button,
        Dict, Bool, Unicode, Property, Int, on_trait_change)
from enthought.traits.ui.api import CodeEditor

from enthought.traits.ui.api import View, Item
from enthought.tvtk.common import camel2enthought


################################################################################
# `_RegistryData` class.
################################################################################ 
class _RegistryData(HasTraits):
    # Object's script ID
    script_id = Str

    # Path to object in object hierarchy.
    path = Str

    # List of traits we are listening for on this object.
    names = List(Str)

    # Nested recordable instances on the object.
    sub_recordables = List(Str)

    # List of traits that are lists.
    list_names = List(Str)


################################################################################
# `RecorderError` class.
################################################################################ 
class RecorderError(Exception):
    pass


################################################################################
# `Recorder` class.
################################################################################ 
class Recorder(HasTraits):

    # The lines of code recorded.
    lines = List(Str)

    # Are we recording or not?
    recording = Bool(False)

    # The Python script we have recorded so far.  This is just a
    # convenience trait for the `get_code()` method.
    script = Property(Unicode)

    ########################################
    # Private traits.

    # Dict used to store information on objects registered.  It stores a
    # unique name for the object and its path in the object hierarchy
    # traversed.
    _registry = Dict

    # Reverse registry with keys as script_id and object as value.
    _reverse_registry = Dict

    # A mapping to generate unique names for objects.
    _name_map = Dict(Str, int)

    # What are the known names in the script?  By known names we mean
    # names which are actually bound to objects.
    _known_ids = List(Str)

    # The known types in the namespace.
    _known_types = List(Str)

    # A guard to check if we are currently in a recorded function call,
    # in which case we don't want to do any recording.
    _in_function = Bool(False)

    ######################################################################
    # `Recorder` interface.
    ######################################################################
    def record(self, code):
        """Record a string to be stored to the output file.

        Parameters:
        -----------

        code - A string of text.
        """
        if self.recording and not self._in_function:
            lines = self.lines
            # Analyze the code and add extra code if needed.
            self._analyze_code(code)
            # Add the code.
            lines.append(code)

    def register(self, object, parent=None, trait_name_on_parent='',
                 ignore=None, known=False):
        """Register an object with the recorder.  This sets up the
        object for recording.  
        
        By default all traits (except those starting and ending with
        '_') are recorded.  For attributes that are themselves
        recordable, one may mark traits with a 'record' metadata as
        follows:

        - If metadata `record=False` is set, the nested object will not be
          recorded.

        - If `record=True`, then that object is also recorded if it is
          not `None`.

        If the object is a list or dict that is marked with
        `record=True`, the list is itself not listened to for changes
        but all its contents are registered.

        If the `object` has a trait named `recorder` then this recorder
        instance will be set to it if possible.

        Parameters:
        -----------

        object : Instance(HasTraits)
            The object to register in the registry.

        parent : Instance(HasTraits)
            An optional parent object in which `object` is contained

        trait_name_on_parent : str
            An optional trait name of the `object` in the `parent`.

        ignore : list(str)
            An optional list of trait names on the `object` to be
            ignored.

        known : bool
            Optional specification if the `object` id is known on the
            interpreter.  This is needed if you are manually injecting
            code to define/create an object.
        """
        registry = self._registry

        # Do nothing if the object is already registered.
        if object in registry:
            return

        # When parent is specified the trait_name_on_parent must also be.
        if parent is not None:
            assert len(trait_name_on_parent) > 0

        if ignore is None:
            ignore = []

        if isinstance(object, HasTraits):
            # Always ignore these.
            ignore.extend(['trait_added', 'trait_modified'])

            sub_recordables = object.traits(record=True).keys()
            # Find all the trait names we must ignore.
            ignore.extend(object.traits(record=False).keys())
            # FIXME: Remove the next line when mayavi is fixed to use
            # new code.
            ignore.extend(sub_recordables)
            # The traits to listen for.
            tnames = [t for t in object.trait_names() 
                      if not t.startswith('_') and not t.endswith('_') \
                         and t not in ignore]
            # Find all list traits.
            trts = object.traits()
            list_names = []
            for t in tnames:
                tt = trts[t].trait_type
                if hasattr(tt, 'default_value_type') and \
                        tt.default_value_type == 5:
                    list_names.append(t)
        else:
            # No traits, so we can't do much.
            sub_recordables = []
            tnames = []
            list_names = []

        # Setup the registry data.
        if parent is None:
            sid = self._get_unique_name(object)
            path = ''
        else:
            pdata = self._get_registry_data(parent)
            pid = pdata.script_id
            ppath = pdata.path 
            tnop = trait_name_on_parent
            if '[' in tnop:
                # If the object is a nested object through an iterator,
                # we instantiate it and don't refer to it through the
                # path, this makes scripting convenient.
                sid = self._get_unique_name(object)
                if len(ppath) == 0:
                    path = pid + '.' + tnop
                else:
                    path = ppath + '.' + tnop
            else:
                sid = pid + '.' + tnop
                path = ppath + '.' + tnop

        # Register the object with the data.
        data = _RegistryData(script_id=sid, path=path, names=tnames,
                             sub_recordables=sub_recordables, 
                             list_names=list_names)
        registry[object] = data
        self._reverse_registry[sid] = object

        # Record the script_id if the known argument is explicitly set to
        # True.
        if known:
            self._known_ids.append(sid)

        # Try and set the recorder attribute if necessary.
        if hasattr(object, 'recorder'):
            try:
                object.recorder = self
            except Exception, e:
                msg = "Cannot set 'recorder' trait of object %r: "\
                      "%s"%(object, e)
                warnings.warn(msg, warnings.RuntimeWarning)
        
        if isinstance(object, HasTraits):
            # Add handler for lists.
            for name in list_names:
                object.on_trait_change(self._list_items_listner,
                                       '%s_items'%name)

            # Register all sub-recordables.
            for name in sub_recordables:
                obj = getattr(object, name)
                if isinstance(obj, list):
                    # Don't register the object itself but register its
                    # children.
                    for i, child in enumerate(obj):
                        attr = '%s[%d]'%(name, i)
                        self.register(child, parent=object,
                                      trait_name_on_parent=attr)
                elif obj is not None:
                    self.register(obj, parent=object, 
                                  trait_name_on_parent=name)
                # Listen for changes to the trait itself so the newly
                # assigned object can also be listened to.
                object.on_trait_change(self._object_changed_handler, name)
            # Now add listner for the object itself.
            object.on_trait_change(self._listner, tnames)

    def unregister(self, object):
        """Unregister the given object from the recorder.  This inverts
        the logic of the `register(...)` method.
        """
        registry = self._registry
        # Do nothing if the object isn't registered.
        if object not in registry:
            return

        data = registry[object]

        # Try and unset the recorder attribute if necessary.
        if hasattr(object, 'recorder'):
            try:
                object.recorder = None
            except Exception, e:
                msg = "Cannot unset 'recorder' trait of object %r:"\
                      "%s"%(object, e)
                warnings.warn(msg, warnings.RuntimeWarning)

        if isinstance(object, HasTraits):
            # Remove all list_items handlers.
            for name in data.list_names:
                object.on_trait_change(self._list_items_listner,
                                       '%s_items'%name, remove=True)

            # Unregister all sub-recordables.
            for name in data.sub_recordables:
                obj = getattr(object, name)
                if isinstance(obj, list):
                    # Unregister the children.
                    for i, child in enumerate(obj):
                        self.unregister(child)
                elif obj is not None:
                    self.unregister(obj)
                # Remove the trait handler for trait assignments.
                object.on_trait_change(self._object_changed_handler,
                                       name, remove=True)
            # Now remove listner for the object itself.
            object.on_trait_change(self._listner, data.names, remove=True)

        # Remove the object data from the registry etc.
        if data.script_id in self._known_ids:
            self._known_ids.remove(data.script_id)
        del self._reverse_registry[data.script_id]
        del registry[object]

    def save(self, file):
        """Save the recorded lines to the given file.  It does not close
        the file.
        """
        file.write(self.get_code())
        file.flush()

    def record_function(self, func, args, kw):
        """Record a function call given the function and its
        arguments."""
        if self.recording and not self._in_function:
            # Record the function name and arguments.
            call_str = self._function_as_string(func, args, kw)
            # Call the function.
            try:
                self._in_function = True
                result = func(*args, **kw)
            finally:
                self._in_function = False

            # Register the result if it is not None.
            if func.__name__ == '__init__':
                f_self = args[0]
                code = self._import_class_string(f_self.__class__)
                self.lines.append(code)
                return_str = self._registry.get(f_self).script_id
            else:
                return_str = self._return_as_string(result)
            if len(return_str) > 0:
                self.lines.append('%s = %s'%(return_str, call_str))
            else:
                self.lines.append('%s'%(call_str))
        else:
            result = func(*args, **kw)
        return result

    def ui_save(self):
        """Save recording to file, pop up a UI dialog to find out where
        and close the file when done.
        """
        from enthought.pyface.api import FileDialog, OK
        wildcard = 'Python files (*.py)|*.py|' + FileDialog.WILDCARD_ALL
        dialog = FileDialog(title='Save Script',
                            action='save as', wildcard=wildcard
                            )
        if dialog.open() == OK:
            fname = dialog.path
            f = open(fname, 'w')
            self.save(f)
            f.close()

    def clear(self):
        """Clears all previous recorded state and unregisters all
        registered objects."""
        # First unregister any registered objects.
        registry = self._registry
        while len(registry) > 0:
            self.unregister(registry.keys()[0])
        # Clear the various lists.
        self.lines[:] = []
        self._registry.clear()
        self._known_ids[:] = []
        self._name_map.clear()
        self._reverse_registry.clear()

    def get_code(self):
        """Returns the recorded lines as a string of printable code."""
        return '\n'.join(self.lines) + '\n'

    def is_registered(self, object):
        """Returns True if the given object is registered with the
        recorder."""
        return object in self._registry

    def get_script_id(self, object):
        """Returns the script_id of a registered object.  Useful when
        you want to manually add a record statement."""
        return self._get_registry_data(object).script_id

    def get_object_path(self, object):
        """Returns the path in the object hierarchy of a registered
        object.  Useful for debugging."""
        return self._get_registry_data(object).path

    def write_script_id_in_namespace(self, script_id):
        """If a script_id is not known in the current script's namespace,
        this sets it using the path of the object or actually
        instantiating it.  If this is not possible (since the script_id
        matches no existing object), nothing is recorded but the
        framework is notified that the particular script_id is available
        in the namespace.  This is useful when you want to inject code
        in the namespace to create a particular object.
        """
        if not self.recording:
            return
        known_ids = self._known_ids
        if script_id not in known_ids:
            obj = self._reverse_registry.get(script_id)
            # Add the ID to the known_ids.
            known_ids.append(script_id)
            if obj is not None:
                data = self._registry.get(obj)
                result = ''
                if len(data.path) > 0:
                    # Record code for instantiation of object.
                    result = '%s = %s'%(script_id, data.path)
                else:
                    # This is not the best thing to do but better than
                    # nothing.
                    result = self._import_class_string(obj.__class__)
                    cls = obj.__class__.__name__
                    mod = obj.__module__
                    result += '\n%s = %s()'%(script_id, cls)

                if len(result) > 0:
                    self.lines.extend(result.split('\n'))

    ######################################################################
    # Non-public interface.
    ###################################################################### 
    def _get_unique_name(self, obj):
        """Return a unique object name (a string).  Note that this does
        not cache the object, so if called with the same object 3 times
        you'll get three different names.
        """
        cname = obj.__class__.__name__
        nm = self._name_map
        result = ''
        builtin = False
        if cname in __builtin__.__dict__:
            builtin = True
            if hasattr(obj, '__name__'):
                cname = obj.__name__
        else:
            cname = camel2enthought(cname)

        if cname in nm:
            id = nm[cname] + 1
            nm[cname] = id
            result = '%s%d'%(cname, id)
        else:
            nm[cname] = 0
            # The first id doesn't need a number if it isn't builtin.
            if builtin:
                result = '%s0'%(cname)
            else:
                result = cname
        return result

    def _get_registry_data(self, object):
        """Get the data for an object from registry."""
        data = self._registry.get(object)
        if data is None:
            msg = "Recorder: Can't get script_id since object %s not registered"
            raise RecorderError(msg%(object))
        return data

    def _listner(self, object, name, old, new):
        """The listner for trait changes on an object.
        
        This is called by child listners or when any of the recordable
        object's traits change when recording to a script is enabled.

        Parameters:
        -----------

        recordable : The object which implements IRecordable.

        obj : Object which has changed.

        name : extended name of attribute that changed.

        old : Old value.

        new : New value.

        """
        if self.recording and not self._in_function:
            new_repr = repr(new)
            sid = self._get_registry_data(object).script_id
            if len(sid) == 0:
                msg = '%s = %r'%(name, new)
            else:
                msg = '%s.%s = %r'%(sid, name, new)
            if new_repr.startswith('<') and new_repr.endswith('>'):
                self.record('# ' + msg)
            else:
                self.record(msg)

    def _list_items_listner(self, object, name, old, event):
        """The listner for *_items on list traits of the object.
        """
        if self.recording and not self._in_function:
            sid = self._get_registry_data(object).script_id
            index = event.index
            removed = event.removed
            nr = len(removed)
            slice = '[%d:%d]'%(index, index + nr)
            added = event.added
            na = len(added)
            rhs = [self._object_as_string(item) for item in added]
            rhs = ', '.join(rhs)
            obj = '%s.%s'%(sid, name[:-6])
            msg = '%s%s = [%s]'%(obj, slice, rhs)
            self.record(msg)

    def _object_changed_handler(self, object, name, old, new):
        """Called when a child recordable object has been reassigned."""
        registry = self._registry
        if old is not None:
            if old in registry:
                self.unregister(old)
        if new is not None:
            if new not in registry:
                self.register(new, parent=object,
                              trait_name_on_parent=name)

    def _get_script(self):
        return self.get_code()

    def _analyze_code(self, code):
        """Analyze the code and return extra code if needed.
        """
        known_ids = self._known_ids
        lhs = ''
        try:
            lhs = code.split()[0]
        except IndexError:
            pass

        if '.' in lhs:
            ob_name = lhs.split('.')[0]
            self.write_script_id_in_namespace(ob_name)

    def _function_as_string(self, func, args, kw):
        """Return a string representing the function call."""
        func_name = func.__name__
        func_code = func.func_code
        # Even if func is really a decorated method it never shows up as
        # a bound or unbound method here, so we have to inspect the
        # argument names to figure out if this is a method or function.
        if func_code.co_argcount > 0 and \
           func_code.co_varnames[0] == 'self':
            # This is a method, the first argument is bound to self.
            f_self = args[0]
            # Convert the remaining arguments to strings.
            argl = [self._object_as_string(arg) for arg in args[1:]]

            # If this is __init__ we special case it.
            if func_name == '__init__':
                # Register the object.
                self.register(f_self, known=True)
                func_name = f_self.__class__.__name__
            else:
                sid = self._object_as_string(f_self)
                func_name = '%s.%s'%(sid, func_name)
        else:
            argl = [self._object_as_string(arg) for arg in args]

        # Convert the keyword args.
        kwl = ['%s=%s'%(key, self._object_as_string(value)) 
               for key, value in kw.iteritems()]
        argl.extend(kwl)

        # Make a string representation of the args, kw.
        argstr = ', '.join(argl)
        return '%s(%s)'%(func_name, argstr)

    def _object_as_string(self, object):
        """Return a string representing the object.
        """
        registry = self._registry
        if object in registry:
            # Return script id if the object is known; create the script
            # id on the namespace if needed before that.
            sid = registry.get(object).script_id
            self.write_script_id_in_namespace(sid)
            return sid
        else:
            # Try and return the object.
            ob_id = id(object)
            orepr = repr(object)
            # As done in appscripting, we assume that if the hexid of
            # the object is in its string representation then it is an
            # arbitrary object.
            if hex(ob_id) not in orepr:
                return orepr

        # FIXME: Should we instead just create the object here?
        raise ValueError('Unable to represent object %r in script'%object)

    def _return_as_string(self, object):
        """Return a string given a returned object from a function.
        """
        result = ''
        ignore = (types.FloatType, types.ComplexType, types.BooleanType,
                  types.IntType, types.LongType) + types.StringTypes
        if object is not None and type(object) not in ignore:
            # If object is not know, register it.
            registry = self._registry
            if object not in registry:
                self.register(object)
            result = registry.get(object).script_id
            # Since this is returned it is known on the namespace.
            known_ids = self._known_ids
            if result not in known_ids:
                known_ids.append(result)
        return result

    def _import_class_string(self, cls):
        """Import a class if needed.
        """
        cname = cls.__name__
        result = ''
        if cname not in __builtin__.__dict__:
            mod = cls.__module__
            typename = '%s.%s'%(mod, cname)
            if typename not in self._known_types:
                result = 'from %s import %s'%(mod, cname)
                self._known_types.append(typename)
        return result

################################################################################
# `RecorderWithUI` class.
################################################################################ 
class RecorderWithUI(Recorder):
    """
    This class represents a Recorder but with a simple user interface.
    """

    # The code to display
    code = Code(editor=CodeEditor(line='current_line'))

    # Button to save script to file.
    save_script = Button('Save Script')

    # The current line to show, used by the editor.
    current_line = Int

    view = View(Item('code', show_label=False), 
                Item('save_script', show_label=False),
                width=600, height=400,
                buttons=['OK'], resizable=True)

    @on_trait_change('lines[]')
    def _update_code(self):
        self.code = self.get_code()
        self.current_line = len(self.lines) + 1

    def _save_script_fired(self):
        self.ui_save()


################################################################################
# Utility functions. 
################################################################################

# The global recorder.
_recorder = None

def get_recorder():
    """Return the global recorder.  Does not create a new one if none
    exists.
    """
    return _recorder

def set_recorder(rec):
    """Set the global recorder instance.
    """
    global _recorder
    _recorder = rec

# Guard to ensure that only the outermost recordable call is recorded
# and nested calls ignored.
_outermost_call = True

def recordable(func):
    """A decorator that wraps a function into one that is recordable.

    This will record the function only if the global recorder has been
    set via a `set_recorder` function call.

    This is almost entirely copied from the
    enthought.appscripting.scriptable.scriptable decorator.  
    """
    
    def _wrapper(*args, **kw):
        """A wrapper returned to replace the decorated function."""
        global _outermost_call

        # Boolean to specify if the method was recorded or not.
        record = False
        if _outermost_call:
            _outermost_call = False
            # Get the recorder.
            rec = get_recorder()
            if rec is not None:
                # Record the method if recorder is available.
                record = True
                try:
                    result = rec.record_function(func, args, kw)
                finally:
                    _outermost_call = True
        if not record:
            # If the method was not recorded, just call it.
            result = func(*args, **kw)

        return result

    # Mimic the actual function.
    _wrapper.__name__ = func.__name__
    _wrapper.__doc__ = func.__doc__
    _wrapper.__dict__.update(func.__dict__)

    return _wrapper


def start_recording(object, ui=True, known=True):
    """Convenience function to start recording.  Returns the recorder.

    Parameters:

    object :  object to record.
    ui : bool specifying if a UI is to be shown or not
    known : bool specifying if the object is known in the script
    namespace.
    """
    if ui:
        r = RecorderWithUI()
        r.edit_traits(kind='live')
    else:
        r = Recorder()
    r.recording = True
    r.register(object, known=known)
    return r

def stop_recording(object, recorder=None):
    """Stop recording the object given the recorder.  This will pop up a
    UI to ask where to save the script.  If recorder is not passed it
    will try to get it assuming that the object has a recorder trait.
    """
    if recorder is None:
        if hasattr(object, 'recorder'):
            recorder = object.recorder
        else:
            raise RecorderError('Unable to find recorder to stop!')
    recorder.unregister(object)
    recorder.recording = False
    recorder.ui_save()
