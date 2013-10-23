# -*- coding: utf-8 -*-
import sys
import numpy as np
import threading
import serial
import os

from enthought.traits.api import *
from enthought.traits.ui.api import *
from enthought.traits.ui.menu import Action, ToolBar
from enthought.enable.api import Window, Component, ComponentEditor
from enthought.chaco.api import Plot, ArrayPlotData, VPlotContainer

MIN_FREQUENCY = 10000
MAX_FREQUENCY = 40000

class DemoHandler(Handler):
    def closed(self, info, is_ok):
        info.object.finish_event.set()
        info.object.thread.join()        
        return

class Demo(HasTraits):
    plot = Instance(Component)
    received = Int
    wasted = Int
    record = Button("Record")
    stop = Button("Stop")
    load = Button("Load")
    foreward = Button("Foreward")
    backward = Button("Backward")
    sample_size = Int(132)  #1024
    filename = File
    saved_record_index_label = Str
    saved_record_index = 0
    saved_record = None
    traits_view = View(
        VGroup(
            VGroup(
                Item('received', style="readonly"),
                Item('wasted', style="readonly"),
                Item(name='sample_size', style = "readonly"),
                Item('filename', style = 'simple'),
                HGroup(
                    Item("record", show_label = False, enabled_when = "file is None"),
                    Item("stop", show_label = False, enabled_when = "file is not None"),
                    Item("load", show_label = False, enabled_when = "file is None and os.path.exists(filename)"),
                    Item("foreward", show_label = False, enabled_when = "file is not None and file_is_readonly == True"),
                    Item("backward", show_label = False, enabled_when = "file is not None and file_is_readonly == True"),
                    Item("saved_record_index_label", show_label = False, visible_when = "file is not None and file_is_readonly == True", style = "readonly"),
                ),
            ),
            Item('plot', editor=ComponentEditor(), show_label=False), orientation = "vertical"),

        resizable=True, title="Spectrum",
        width=1200, height=500,
        handler=DemoHandler
    )
    def _record_fired(self):
        print "RECORDING"
        self.file_is_readonly = False
        if self.filename == "":
            self.filename = "tmp.csv"
        print self.filename
        self.received = 0
        self.wasted = 0
        self.file = open(self.filename, "w")
    def _stop_fired(self):
        print "STOPPED"
        self.file.close()
        self.file = None
        self.file_is_readonly = False
    def _load_fired(self):
        print "LOADING"
        self.file_is_readonly = True
        self.saved_record_index = 0
        self.file = open(self.filename, "r")
        self.saved_record = self.file.readlines()
        if len(self.saved_record) > 0:
            tmp = [int(i) for i in self.saved_record[self.saved_record_index].split(",")]
            self.data['amplitude'] = np.array(tmp, dtype = np.float)
            self.saved_record_index_label = str(self.saved_record_index + 1) +"/"+ str(len(self.saved_record))
        else:
            self.saved_record_index_label = "0 / 0"
        
    def _foreward_fired(self):
        if self.saved_record_index < len(self.saved_record) - 1:
            self.saved_record_index += 1
            tmp = [int(i) for i in self.saved_record[self.saved_record_index].split(",")]
            self.data['amplitude'] = np.array(tmp, dtype = np.float)
            self.saved_record_index_label = str(self.saved_record_index + 1) +"/"+ str(len(self.saved_record))
            print "FOREWARD"
    def _backward_fired(self):
        if self.saved_record_index > 0:
            self.saved_record_index -= 1
            tmp = [int(i) for i in self.saved_record[self.saved_record_index].split(",")]
            self.data['amplitude'] = np.array(tmp, dtype = np.float)
            self.saved_record_index_label = str(self.saved_record_index + 1) +"/"+ str(len(self.saved_record))
            print "BACKWARD"
        
    def __init__(self, **traits):
        super(Demo, self).__init__(**traits)
        self.file = None
        self.file_is_readonly = False
        self.data = ArrayPlotData()
        self.data["frequency"] = np.linspace(MIN_FREQUENCY, MAX_FREQUENCY, num=self.sample_size)
        self.data['amplitude'] = np.zeros(self.sample_size)
        self.plot = self._create_plot_component()
        self.finish_event = threading.Event()        
        self.thread = threading.Thread(target=self.get_serial_data)
        self.thread.start()
        
    def _create_plot_component(self):
        spectrum_plot = Plot(self.data)
        spectrum_plot.plot(("frequency", "amplitude"), name="Spectrum", color=(1, 0, 0), line_width=2)
        spectrum_plot.padding_bottom = 20
        spectrum_plot.padding_top = 20
        spectrum_plot.index_range.low = MIN_FREQUENCY
        spectrum_plot.index_range.high = MAX_FREQUENCY
        spec_range = spectrum_plot.plots.values()[0][0].value_mapper.range
        spec_range.low = 0.0
        spec_range.high = 65536.0
        spectrum_plot.index_axis.title = 'Frequency(Hz)'
        spectrum_plot.value_axis.title = 'Amplitude(dB)'

        container = VPlotContainer()
        container.add(spectrum_plot)
        return container        

    def get_serial_data(self):
        state = 0
        ser = serial.Serial(3, 115200, timeout = 1)
        data = []
        z = "p"
        while not self.finish_event.is_set():
            x = ser.read()
            if self.file is not None and self.file_is_readonly == True: #when playing saved data
                continue
            if len(x) == 0:
                state = 0
            elif z == "$" or x == "D":
                state = 1
                if len(data) > 0:
                    if len(data) == self.sample_size:
                        self.received += 1
                        if self.file is not None:   #when recording real-time data
                            self.file.write(",".join([str(i) for i in data]) + "\n")
                        self.data['amplitude'] = np.array(data, dtype = np.float)
                        self._create_plot_component()
                    else:
                        self.wasted += 1
                    data = []
            elif x == 0x0a:
                state = 0
            elif state == 1:
                lowByte = x
                state = 2
            elif state == 2:
                value = ord(lowByte) + ord(x) * 256
                data.append(value)
                state = 1
            else:
                pass
            z = x
            
if __name__ == "__main__":
    a = "default"
    while not a.isdigit():
        a = raw_input("Sample size: ")
    demo = Demo()
    demo.sample_size = int(a)
    demo.configure_traits()

