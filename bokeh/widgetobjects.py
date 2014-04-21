import six
from .plotobject import PlotObject
#from .objects import DataSource
from .properties import (HasProps, Dict, Enum, Either, Float, Instance, Int, List,
    String, Color, Include, Bool, Tuple, Any, Date, lookup_descriptor)
from .pivot_table import pivot_table
import copy
import logging
logger = logging.getLogger(__name__)

import pandas as pd

class Panel(PlotObject):
    title = String
    child = Instance(PlotObject, has_ref=True)
    closable = Bool(False)

class Tabs(PlotObject):
    tabs = List(Instance(Panel, has_ref=True), has_ref=True)

class HBox(PlotObject):
    children = List(Instance(PlotObject, has_ref=True), has_ref=True)
class VBox(PlotObject):
    children = List(Instance(PlotObject, has_ref=True), has_ref=True)

#parent class only, you need to set the fields you want
class VBoxModelForm(PlotObject):
    _children  = List(Instance(PlotObject, has_ref=True), has_ref=True)
    _field_defs = Dict(String, Any)
    input_specs = None
    jsmodel = "VBoxModelForm"
    def __init__(self, *args, **kwargs):
        super(VBoxModelForm, self).__init__(*args, **kwargs)
        for prop in self.properties():
            propobj = lookup_descriptor(self.__class__, prop)
            if isinstance(propobj, Float):
                self._field_defs[prop] = "Float"
            elif isinstance(propobj, Int):
                self._field_defs[prop] = "Int"
            else:
                self._field_defs[prop] = "String"
    def create_inputs(self, session):
        session.add(self)
        if self.input_specs:
            for input_spec in self.input_specs:
                input_spec = copy.copy(input_spec)
                widget = input_spec.pop('widget')
                widget = widget.create(**input_spec)
                session.add(widget)
                self._children.append(widget)


class InputWidget(PlotObject):
    title = String()
    name = String()
    value = String()
    @classmethod
    def coerce_value(cls, val):
        prop_obj = lookup_descriptor(cls, 'value')
        if isinstance(prop_obj, Float):
            return float(val)
        elif isinstance(prop_obj, Int):
            return int(val)
        elif isinstance(prop_obj, String):
            return str(val)
        else:
            return val

    @classmethod
    def create(cls, *args, **kwargs):
        """Only called the first time we make an object,
        whereas __init__ is called every time it's loaded
        """
        if kwargs.get('title') is None:
            kwargs['title'] = kwargs['name']
        if kwargs.get('value') is not None:
            kwargs['value'] = cls.coerce_value(kwargs.get('value'))
        return cls(**kwargs)

class TextInput(InputWidget):
    value = String()

class BokehApplet(PlotObject):
    modelform = Instance(VBoxModelForm, has_ref=True)
    children = List(Instance(PlotObject, has_ref=True), has_ref=True)
    jsmodel = "HBox"
    extra_generated_classes = List(Tuple(String, String, String))

    def update(self, **kwargs):
        super(BokehApplet, self).update(**kwargs)
        self.setup_events()

    def setup_events(self):
        if self.modelform:
            self.bind_modelform()

    def bind_modelform(self):
        for prop in self.modelform.__properties__:
            if not prop.startswith("_"):
                self.modelform.on_change(prop, self,
                                         'input_change')

    def input_change(self, obj, attrname, old, new):
        pass

    def create(self):
        pass
    def add_all(self, session):
        objs = self.references()
        for obj in objs:
            session.add(obj)

    @classmethod
    def add_route(cls, route, bokeh_url):
        from bokeh.server.app import bokeh_app
        from bokeh.pluginutils import app_document
        from bokeh.plotting import session
        from flask import render_template
        @app_document(cls.__view_model__, bokeh_url)
        def make_app():
            app = cls()
            app.create(session())
            return app

        def exampleapp():
            app = make_app()
            docname = session().docname
            docid = session().docid
            extra_generated_classes = app.extra_generated_classes
            if len(extra_generated_classes) == 0:
                extra_generated_classes.append((
                    app.__view_model__,
                    app.__view_model__,
                    app.jsmodel))
                extra_generated_classes.append((
                    app.modelform.__view_model__,
                    app.modelform.__view_model__,
                    app.modelform.jsmodel))
            return render_template(
                'applet.html',
                extra_generated_classes=extra_generated_classes,
                title=app.__class__.__view_model__,
                docname=docname,
                docid=docid,
                splitjs=bokeh_app.splitjs)
        exampleapp.__name__ = cls.__view_model__
        bokeh_app.route(route)(exampleapp)

class Paragraph(PlotObject):
    text = String()

class PreText(Paragraph):
    pass

class Select(InputWidget):
    options = List(Either(String(), Dict(String(), String())))
    value = String()

    @classmethod
    def create(self, *args, **kwargs):
        options = kwargs.pop('options', [])
        new_options = []
        for opt in options:
            if isinstance(opt, six.string_types):
                opt = {'name' : opt, 'value' : opt}
            new_options.append(opt)
        kwargs['options'] = new_options
        return super(Select, self).create(*args, **kwargs)

class Slider(InputWidget):
    value = Float()
    start = Float()
    end = Float()
    steps = Int(default=50)
    orientation = Enum("horizontal", "vertical")

class DatePicker(InputWidget):
    value = Date
    min_date = Date(default=None)
    max_date = Date(default=None)

class TableWidget(PlotObject):
    pass

class TableColumn(PlotObject):
    type = Enum("string", "numeric", "date")
    data = String
    header = String

class HandsonTable(TableWidget):
    #source = Instance(DataSource, has_ref=True)
    source = Instance(".objects.DataSource", has_ref=True)
    columns = List(Instance(TableColumn, has_ref=True), has_ref=True)

class ObjectExplorer(PlotObject):
    data_widget = Instance(TableWidget, has_ref=True)

class DataTable(PlotObject):
    #source = Instance(DataSource, has_ref=True)
    source = Instance(".objects.DataSource", has_ref=True)
    sort = List(String)
    group = List(String)
    offset = Int(default=0)
    length = Int(default=100)
    maxlength = Int
    totallength = Int
    tabledata = Dict(String, Any)
    filterselected = Bool(default=False)

    def setup_events(self):
        self.on_change('sort', self, 'get_data')
        self.on_change('group', self, 'get_data')
        self.on_change('length', self, 'get_data')
        self.on_change('offset', self, 'get_data')
        self.on_change('filterselected', self, 'get_data')
        self.source.on_change('selected', self, 'get_data')
        self.source.on_change('data', self, 'get_data')
        self.source.on_change('computed_columns', self, 'get_data')
        if not self.tabledata:
            self.get_data()

    def transform(self):
        return dict(sort=self.sort,
                    group=self.group,
                    offset=self.offset,
                    length=self.length,
                    filterselected=self.filterselected,
                    )

    def setselect(self, select):
        self.source.setselect(select, self.transform())
        self.get_data()

    def select(self, select):
        self.source.select(select, self.transform())
        self.get_data()

    def deselect(self, deselect):
        self.source.deselect(deselect, self.transform())
        self.get_data()

    def get_data(self, obj=None, attrname=None, old=None, new=None):
        data = self.source.get_data(self.transform())
        self.maxlength = data.pop('maxlength')
        self.totallength = data.pop('totallength')
        self.tabledata = data

class PivotTable(PlotObject):
    #source = Instance(DataSource, has_ref=True)
    source = Instance(".objects.DataSource", has_ref=True)
    title = String("Pivot Table")
    description = String("")
    data = Dict(String, Any)
    fields = List(Any) # List[{name: String, dtype: String}]
    rows = List(Any)
    columns = List(Any)
    values = List(Any)
    filters = List(Any)
    manual_update = Bool(True)

    def setup_events(self):
        self.on_change('rows', self, 'get_data')
        self.on_change('columns', self, 'get_data')
        self.on_change('values', self, 'get_data')
        self.on_change('filters', self, 'get_data')

        if not self.data:
            self.get_data()

    def get_data(self, obj=None, attrname=None, old=None, new=None):
        self.data = self.pivot_table()

    def _pivot_table(self, rows, cols, values, aggfunc=None):
        dataset = pd.DataFrame(self.source.data)

        try:
            if not rows and not cols:
                table = pd.DataFrame()
            else:
                table = pivot_table(dataset, rows=rows, cols=cols, values=values, aggfunc=aggfunc)
        except:
            table = pd.DataFrame()

        if isinstance(table, pd.DataFrame):
            if len(rows) == 1:
                _rows = [ [x] for x in table.index.tolist() ]
            else:
                _rows = table.index.tolist()
            if len(cols) == 1:
                _cols = [ [x] for x in table.columns.tolist() ]
            else:
                _cols = table.columns.tolist()
            _values = table.values.tolist()
            _attrs = dataset.columns.tolist()
        elif isinstance(table, pd.Series):
            raise ValueError("series")
        else:
            raise ValueError("???")

        return table, (_attrs, _rows, _cols, _values)

    def pivot_table(self):
        def fields(items):
           return [ item["field"] for item in items ]

        row_fields = fields(self.rows)
        column_fields = fields(self.columns)
        value_fields = fields(self.values)
        filter_fields = fields(self.filters)

        if len(self.values) > 0:
            aggfunc = values[0]["aggregate"]
        else:
            aggfunc = len

        _, (_attrs, _rows, _cols, _values) = self._pivot_table(row_fields, column_fields, value_fields, aggfunc)

        return dict(
            attrs  = _attrs,
            rows   = _rows,
            cols   = _cols,
            values = _values,
        )
