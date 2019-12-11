#!/usr/bin/python3
#
# copyright by Oliver Dippel o.dippel@gmx.de 2019
#

import threading
import serial
import os
import copy
import sys
import glob
import datetime
import time
import argparse
import json
import gi
gi.require_version('Gtk', '3.0') 
from gi.repository import Gtk, GdkPixbuf, Gdk, Pango, Gio, GObject
from gi.repository.GdkPixbuf import Pixbuf, InterpType
import cairo
from io import StringIO

#
# OVP:25.2, OCP:5.10, OPP:35.50, LVP:01.5,OAH:0.000,OHP:00:00
# 
# start
# stop
# on
# off
# x.xxA
# LVP:xx.x
# OVP:xx.x
# OCP:x.xx
# OPP:xx.xx
# OAH:x.xxx
# OHP:xx:xx
# read
# 


class MyGui(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self)
		if len(sys.argv) != 2:
			print("")
			print("USAGE:")
			print("	" + sys.argv[0] + " SERIAL_PORT")
			print("")
			exit(1)
		self.port = sys.argv[1]
		self.baud = 9600
		self.serial = serial.Serial(self.port, self.baud, timeout=10)
		thread = threading.Thread(target=self.read_from_port)
		thread.start()
   
	def read_from_port(self):
		self.running = True
		time.sleep(0.2)
		self.serial.write("read".encode())
		time.sleep(0.2)
		self.serial.write("start".encode())
		while self.running == True:
			reading = self.serial.readline().decode().strip()
			if reading.startswith("OVP:"):
				for part in reading.split(","):
					name = part.split(":")[0].strip()
					value = part.split(":", 1)[1].strip()
					if name == "LVP":
						self.lvp.set_text(value)
					if name == "OVP":
						self.ovp.set_text(value)
					if name == "OCP":
						self.ocp.set_text(value)
					if name == "OPP":
						self.opp.set_text(value)
					if name == "OAH":
						self.oah.set_text(value)
					if name == "OHP":
						self.ohp.set_text(value)
			elif "Ah," in reading:
				timestamp = time.time()
				voltage = reading.split(",")[0]
				ampere = reading.split(",")[1]
				capacity = reading.split(",")[2]
				distime = reading.split(",")[3]
				self.timedata.append([timestamp, float(voltage.strip("V")), float(ampere.strip("A")), float(capacity.strip("Ah")), distime])
				self.samples.set_markup("<span size='xx-large'>Samples: " + str(len(self.timedata)) + "</span>")
				self.voltage.set_markup("<span foreground='blue' size='xx-large'>Voltage: " + voltage + "</span>")
				self.ampere.set_markup("<span foreground='red' size='xx-large'>Ampere: " + ampere + "</span>")
				self.capacity.set_markup("<span foreground='#ab00ab' size='xx-large'>Capacity: " + capacity + "</span>")
				self.time.set_markup("<span foreground='yellow' size='xx-large'>Time: " + distime + "</span>")
				self.timeline.queue_draw()
			else:
				print(reading)
				self.stat.set_text(reading)

	def do_activate(self):
		self.timedata = []
		self.window = Gtk.ApplicationWindow(application=self)
		self.window.connect("destroy", self.quit_callback)
		titlebar = self.create_titlebar()
		self.window.set_titlebar(titlebar)

		mainbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		self.window.add(mainbox)

		mainbox2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		mainbox.pack_start(mainbox2, True, True, 0)

		timevaluebox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		mainbox2.pack_start(timevaluebox, True, True, 0)

		timeline = self.create_timeline()
		timevaluebox.pack_start(timeline, True, True, 0)

		valuebox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		timevaluebox.add(valuebox)
		self.samples = Gtk.Label("--")
		valuebox.pack_start(self.samples, True, True, 0)
		self.voltage = Gtk.Label("--")
		valuebox.pack_start(self.voltage, True, True, 0)
		self.ampere = Gtk.Label("--")
		valuebox.pack_start(self.ampere, True, True, 0)
		self.capacity = Gtk.Label("--")
		valuebox.pack_start(self.capacity, True, True, 0)
		self.time = Gtk.Label("--")
		valuebox.pack_start(self.time, True, True, 0)

		buttonbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		mainbox.add(buttonbox)
		btn_start = Gtk.Button.new_with_label("Start")
		btn_start.connect("clicked", self.btn_start)
		buttonbox.pack_start(btn_start, True, True, 0)
		btn_stop = Gtk.Button.new_with_label("Stop")
		btn_stop.connect("clicked", self.btn_stop)
		buttonbox.pack_start(btn_stop, True, True, 0)
		btn_on = Gtk.Button.new_with_label("On")
		btn_on.connect("clicked", self.btn_on)
		buttonbox.pack_start(btn_on, True, True, 0)
		btn_off = Gtk.Button.new_with_label("Off")
		btn_off.connect("clicked", self.btn_off)
		buttonbox.pack_start(btn_off, True, True, 0)
		btn_read = Gtk.Button.new_with_label("Read")
		btn_read.connect("clicked", self.btn_read)
		buttonbox.pack_start(btn_read, True, True, 0)

		settingbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
		mainbox2.add(settingbox)

		self.load = self.add_setting(settingbox, "Ampere", "0.50", self.load_set)
		self.lvp = self.add_setting(settingbox, "LVP", "", self.lvp_set)
		self.ovp = self.add_setting(settingbox, "OVP", "", self.ovp_set)
		self.ocp = self.add_setting(settingbox, "OCP", "", self.ocp_set)
		self.opp = self.add_setting(settingbox, "OPP", "", self.opp_set)
		self.oah = self.add_setting(settingbox, "OAH", "", self.oah_set)
		self.ohp = self.add_setting(settingbox, "OHP", "", self.ohp_set)
		self.stat = Gtk.Label("--")
		settingbox.pack_start(self.stat, True, True, 0)
		self.window.show_all()

	def add_setting(self, settingbox, label, value, callback):
		box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		settingbox.add(box)
		label = Gtk.Label(label)
		box.pack_start(label, True, True, 0)
		entry = Gtk.Entry()
		entry.set_text(value)
		box.pack_start(entry, True, True, 0)
		btn_set = Gtk.Button.new_with_label("SET")
		btn_set.connect("clicked", callback)
		box.pack_start(btn_set, True, True, 0)
		return entry

	def load_set(self, button):
		data = "%1.02fA" % (float(self.load.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())

	def lvp_set(self, button):
		data = "LVP:%0.1f" % (float(self.lvp.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def ovp_set(self, button):
		data = "OVP:%0.1f" % (float(self.ovp.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def ocp_set(self, button):
		data = "OCP:%0.2f" % (float(self.ocp.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def opp_set(self, button):
		data = "OPP:%0.2f" % (float(self.opp.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def oah_set(self, button):
		data = "OAH:%0.3f" % (float(self.oah.get_text()), )
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def ohp_set(self, button):
		data = "OHP:" + self.ohp.get_text()
		self.stat.set_text(data)
		self.serial.write(data.encode())
		time.sleep(0.2)
		self.serial.write("read".encode())

	def btn_start(self, button):
		self.stat.set_text("start")
		self.serial.write("start".encode())

	def btn_stop(self, button):
		self.stat.set_text("stop")
		self.serial.write("stop".encode())

	def btn_on(self, button):
		self.stat.set_text("on")
		self.serial.write("on".encode())

	def btn_off(self, button):
		self.stat.set_text("off")
		self.serial.write("off".encode())

	def btn_read(self, button):
		self.stat.set_text("read")
		self.serial.write("read".encode())

	def quit_callback(self, action):
		self.running = False
		self.quit()

	def create_titlebar(self):
		hb = Gtk.HeaderBar()
		hb.set_show_close_button(True)
		hb.props.title = "FZ35 (5A 35W Electronic Load Tester)"
		box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		Gtk.StyleContext.add_class(box.get_style_context(), "linked")
		hb.pack_start(box)
		## Menuheader
		menubutton = Gtk.MenuButton.new()
		menumodel = Gio.Menu()
		menumodel.append("Export", "app.export")
		export_as = Gio.SimpleAction.new("export", None)
		export_as.connect("activate", self.export_as)
		self.add_action(export_as)
		menubutton.set_menu_model(menumodel)
		box.add(menubutton)
		return hb



	def timeline_draw_event(self, da, cairo_ctx):
		self.cw = self.timeline.get_allocation().width
		self.ch = self.timeline.get_allocation().height
		gx = 150
		gw = self.cw - gx - 50
		gh = self.ch - 10 - 10
		dl = len(self.timedata)
		if dl == 0:
			return


		cairo_ctx.set_source_rgb(0.0, 0.0, 0.0)
		cairo_ctx.rectangle(gx - 1, 10 - 1, gw + 1, gh + 1)
		cairo_ctx.fill()

		# Grig
		cairo_ctx.set_source_rgb(0.5, 0.5, 0.5)
		cairo_ctx.set_line_width(0.5)
		for n in range(0, 50, 5):
			y = self.ch - 10 - int(n * gh / 50)
			cairo_ctx.new_path()
			cairo_ctx.move_to(gx, y)
			cairo_ctx.line_to(gx + gw, y)
			cairo_ctx.stroke()

		# Voltage
		cairo_ctx.set_line_width(1.0)
		cairo_ctx.set_source_rgb(0.0, 0.0, 1.0)
		for n in range(0, 30 + 5, 5):
			y = self.ch - 10 - int(n * gh / 30)
			cairo_ctx.move_to(gx + gw + 10, y + 3)
			cairo_ctx.show_text(str(n) + "V")
			cairo_ctx.new_path()
			cairo_ctx.move_to(gx + gw, y)
			cairo_ctx.line_to(gx + gw + 5, y)
			cairo_ctx.stroke()
		cairo_ctx.new_path()
		tn = 1;
		for data in self.timedata:
			x = gx + tn * gw / dl
			y = self.ch - 10 - int(data[1] * gh / 30.0)
			if  tn == 1:
				cairo_ctx.move_to(gx, y)
			cairo_ctx.line_to(x, y)
			tn = tn + 1
		cairo_ctx.stroke()

		# Ampere
		cairo_ctx.set_source_rgb(1.0, 0.0, 0.0)
		for n in range(0, 50 + 10, 10):
			y = self.ch - 10 - int(n * gh / 50)
			cairo_ctx.move_to(10, y + 3)
			cairo_ctx.show_text(str(n / 10.0) + "A")
			cairo_ctx.new_path()
			cairo_ctx.move_to(gx - 5, y)
			cairo_ctx.line_to(gx, y)
			cairo_ctx.stroke()
		cairo_ctx.new_path()
		tn = 1;
		for data in self.timedata:
			x = gx + tn * gw / dl
			y = self.ch - 10 - int(data[2] * gh / 5.0)
			if  tn == 1:
				cairo_ctx.move_to(gx, y)
			cairo_ctx.line_to(x, y)
			tn = tn + 1
		cairo_ctx.stroke()


		# Capacity
		capacity_max = (int(self.timedata[-1][3]) + 1) * 10
		if capacity_max < 5:
			capacity_max = 5
		steps = int(capacity_max / 4)
		scale = 10
		cairo_ctx.set_source_rgb(1.0, 0.0, 1.0)
		for n in range(0, int(capacity_max * scale) + steps, steps):
			y = self.ch - 10 - int(n * gh / capacity_max)
			cairo_ctx.move_to(50, y + 3)
			cairo_ctx.show_text(str(n / scale) + "Ah")
			cairo_ctx.new_path()
			cairo_ctx.move_to(gx - 5, y)
			cairo_ctx.line_to(gx, y)
			cairo_ctx.stroke()
		cairo_ctx.new_path()
		tn = 1;
		for data in self.timedata:
			x = gx + tn * gw / dl
			y = self.ch - 10 - int(data[3] * gh / capacity_max * scale)
			if  tn == 1:
				cairo_ctx.move_to(gx, y)
			cairo_ctx.line_to(x, y)
			tn = tn + 1
		cairo_ctx.stroke()


		# Time
		time_max = int(self.timedata[-1][4].split(":")[0]) * 60 + int(self.timedata[-1][4].split(":")[1]) + 2
		if time_max < 10:
			time_max = 10
		steps = int(time_max / 4)
		scale = 1
		cairo_ctx.set_source_rgb(1.0, 1.0, 0.0)
		for n in range(0, time_max + steps, steps):
			y = self.ch - 10 - int(n * gh / time_max)
			cairo_ctx.move_to(100, y + 3)
			cairo_ctx.show_text(str(int(n / scale)) + "min")
			cairo_ctx.new_path()
			cairo_ctx.move_to(gx - 5, y)
			cairo_ctx.line_to(gx, y)
			cairo_ctx.stroke()
		cairo_ctx.new_path()
		tn = 1;
		for data in self.timedata:
			x = gx + tn * gw / dl
			time_m = int(data[4].split(":")[0]) * 60 + int(data[4].split(":")[1])
			y = self.ch - 10 - int(time_m * gh / time_max * scale)
			if  tn == 1:
				cairo_ctx.move_to(gx, y)
			cairo_ctx.line_to(x, y)
			tn = tn + 1
		cairo_ctx.stroke()


		cairo_ctx.set_source_rgb(0.0, 0.0, 0.0)
		cairo_ctx.rectangle(gx - 1, 10 - 1, gw + 1, gh + 1)
		cairo_ctx.stroke()

	def timeline_configure_event(self, da, event):
		allocation = da.get_allocation()
		self.surface = da.get_window().create_similar_surface(cairo.CONTENT_COLOR, allocation.width, allocation.height)
		cairo_ctx = cairo.Context(self.surface)
		cairo_ctx.set_source_rgb(1, 1, 1)
		cairo_ctx.paint()
		return True

	def create_timeline(self):
		self.timeline = Gtk.DrawingArea()
		self.timeline.set_size_request(800, 200)
		self.timeline.add_events(Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.SCROLL_MASK)
		self.timeline.connect('draw', self.timeline_draw_event)
		self.timeline.connect('configure-event', self.timeline_configure_event)
#		self.timeline.connect('button-press-event', self.timeline_clicked)
		return self.timeline

	def export_as(self, action, parameter):
		dialog = Gtk.FileChooserDialog("Please choose a file", self.window, Gtk.FileChooserAction.SAVE, (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
		filter_xmeml = Gtk.FileFilter()
		filter_xmeml.set_name("CSV-Data")
		filter_xmeml.add_pattern("*.csv")
		dialog.add_filter(filter_xmeml)
		filter_any = Gtk.FileFilter()
		filter_any.set_name("Any files")
		filter_any.add_pattern("*")
		dialog.add_filter(filter_any)
		response = dialog.run()
		if response == Gtk.ResponseType.OK:
			print("CSV-Data save to " + dialog.get_filename())
			filename = dialog.get_filename()
			if not "." in filename:
				filename += ".csv"
			file = open(filename, "w")
			for data in self.timedata:
				line = ""
				for part in data:
					line += str(part) + ";"
				line = line.strip(";")
				file.write(line + "\r\n")
			file.close()
		dialog.destroy()



app = MyGui()

exit_status = app.run()
sys.exit(exit_status)

