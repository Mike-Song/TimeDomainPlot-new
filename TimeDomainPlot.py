import sys, os
from os import path 
import struct
from socket import *  
import numpy as np
import time
import datetime
import threading
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from Ui_TimeDomainPlot import Ui_MainWindow

gSocketHeaderSize = 16
gSocketBodySize = 32 * 1024
gSocketBufSize = gSocketBodySize + gSocketHeaderSize

class UDPSocketClient:
    def __init__(self):
        self.mHost = '192.168.1.6'
        self.mPort = 6000 
        self.mBufSize = gSocketBodySize + gSocketHeaderSize
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket(AF_INET, SOCK_DGRAM)
        self.mData = None
        self.mUDPClient.settimeout(5)

    def setBufSize (self,  bufSize):
        self.mBufSize = bufSize
        
    def sendData(self):
        self.mUDPClient.sendto(self.mData,self.mAddress)
        self.mData = None # Clear data after send out

    def receiveData(self):
       self.mData, self.mAddress = self.mUDPClient.recvfrom(gSocketBufSize)
       return self.mData

class RealTimeThread(threading.Thread):  
    def __init__(self, axes, canvas, cha,  timeout):  
        super(RealTimeThread, self).__init__()  
        self.axes = axes
        self.canvas = canvas
        self.CHA = cha
        self.timeout = timeout 
        self.data = []
        self.stopped = False
        self.sampleRate = mainWindow.getSampleRate()
        self.recordLen = mainWindow.getRecordLength()
        self.volScale = mainWindow.getVoltageScale()
        self.offset = mainWindow.getOffset()
        self.data_ChA = []
        self.data_ChB = []        

    def run(self):  
        def bumatoyuanmaSingle(x):
          if (x > 32767): 
             x = x - 65536 
          return x
   
        def parseData(data, withHead):
            datalist = []
            newdata = data
            if (withHead):
               newdata = data[16:]

            # Save the original payload
            now = datetime.datetime.now()
            currentTime = now.strftime('%Y-%m-%d-%H-%M-%S') 
            rawFileName = "RawIQ-" + currentTime + ".dat"
            rawFile=open(rawFileName,'wb')
            rawFile.write(newdata)
            rawFile.close()

            self.data_ChA  = []
            self.data_ChB = []
            
            for pos in range(0, 31*1024, 32):
                line = newdata[pos:pos+32]
                newline = ''
                # One line data
                for i in range(0, 32, 2):
                   newline =  newline + ("%04x" % int(struct.unpack('H',line[i:i+2])[0]))

                # Get CHA/CHB VALUE BY ABAB...
                for i in range(0,  64,  8):
                    dataA1= newline[i:i+2]
                    dataA2= newline[i+2:i+4]
                    dataA = dataA2 + dataA1
                    dataA = int (dataA,  16)
                    self.data_ChA .append(bumatoyuanmaSingle(dataA))
                    dataB1 = newline[i+4:i+6]
                    dataB2 = newline[i+6:i+8]
                    dataB = dataB2  + dataB1
                    dataB = int (dataB,  16)
                    self.data_ChB .append(bumatoyuanmaSingle(dataB))
            
            # Write into file
            now = datetime.datetime.now()
            currentTime = now.strftime('%Y-%m-%d-%H-%M-%S') 
            FileName_CHA = "ChA-" + currentTime + ".dat"
            File_CHA=open(FileName_CHA,'wb')
            FileName_CHB = "ChB-" + currentTime + ".dat"
            File_CHB=open(FileName_CHB,'wb')
            for pos in range(0, len(self.data_ChA)):
                File_CHA.write(self.data_ChA[pos])
                File_CHB.write(self.data_ChB[pos])
                
            File_CHA.close()
            File_CHB.close()
            
            if (self.CHA):
                return self.data_ChA
            else:
                return self.data_ChB 
        
        def realtimecapture():
          print ("Real Time Capture.......")
          while not self.stopped:
            mainWindow.sendCmdWRREG(0x2,  0x28)
            mainWindow.udpSocketClient.receiveData()
            mainWindow.sendCmdWRREG(0x2,  0x29)
            mainWindow.udpSocketClient.receiveData()
            time.sleep(1)
            mainWindow.sendCmdWRREG(0x2,  0x2a)
            mainWindow.udpSocketClient.receiveData()
            mainWindow.sendCmdRAW_AD_SAMPLE()
            mainWindow.receiveCmdRAW_AD_SAMPLE()
            #mainWindow.udpSocketClient.receiveData()
            # Parse Data...
            data = mainWindow.udpSocketClient.mData
            
            #print  ("Receive Total Length: ", len(data))
            if data:
                self.data = parseData(data, True)
                on_draw(self.axes, self.canvas, self.data)

        def on_draw( axes, canvas, data):
            #x = np.linspace(-self.sampleRate/2, self.sampleRate/2, len(data))  
            x = np.linspace(-self.sampleRate/2, self.sampleRate/2, 500)  
            #x = np.linspace(-self.sampleRate/2, self.sampleRate/2, 1024) 
            # clear the axes and redraw the plot anew
            axes.clear() 
            axes.set_title('Signal')
            axes.set_xlabel('Freqs(Hz)')
            axes.set_ylabel('dBm')

            normalLimY = self.volScale * 100;
            axes.set_ylim(-normalLimY/2 + self.offset, normalLimY/2 + self.offset )
            ymajorLocator = MultipleLocator(200) 
            yminorLocator = MultipleLocator(100) 
#            axes.yaxis.set_major_locator(ymajorLocator)
#            axes.yaxis.set_minor_locator(yminorLocator)
            
            axes.grid(True)
            axes.plot(x, data[:500])
            canvas.draw()

        now = datetime.datetime.now()
        startTime = now.strftime('%Y-%m-%d-%H-%M-%S')
        subthread = threading.Thread(target=realtimecapture)
        subthread.setDaemon(True)  
        subthread.start()  
        
    def stop(self): 
        print ("Stop thread...")
        self.stopped = True  

    def isStopped(self):  
        return self.stopped  

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        self.dpi = 100
        self.signalframe = self.widget_Signal_TimeDomain
        self.figure = Figure((8, 5.5), dpi=self.dpi)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self.signalframe)
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title('Signal')
        self.axes.set_xlabel('Freqs(Hz)')
        self.axes.set_ylabel('dBm')
        plt.subplots_adjust(left=0.2, bottom=0.2, right=0.8, top=0.8, hspace=0.2, wspace=0.3)
        self.figure.tight_layout()# Adjust spaces

        # Init Socket
        self.udpSocketClient = UDPSocketClient()
        
        # Init Length
        self.sendCmdRecordLength()
        
        self.sendCmdWRREG(0x2,  0x20)
        self.udpSocketClient.receiveData()
        self.sendCmdWRREG(0x2,  0x28)
        self.udpSocketClient.receiveData()
        
        #self.NavToolbar = NavigationToolbar(self.canvas, self.signalframe)
        self.addToolBar(QtCore.Qt.RightToolBarArea, NavigationToolbar(self.canvas, self.signalframe))

    def sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16,  cmdData):
          cmdid=struct.pack('H',htons(cmdid))
          status=struct.pack('H',htons(status))
          msgid=struct.pack('H',htons(msgid))
          len=struct.pack('H',htons(len))
          type=struct.pack('H',htons(type))
          offset=struct.pack('H',htons(offset))
          apiversion=struct.pack('B',apiversion) # 1 Byte unsigned char
          pad=struct.pack('B',pad) # 1 Byte unsigned char
          CRC16=struct.pack('H',htons(CRC16)) # 2 Byte unsigned short
          cmdHeader = cmdid + status + msgid + len + type + offset + apiversion + pad + CRC16
          
          if (cmdData != None):
              self.udpSocketClient.mData = cmdHeader + cmdData
          else:
              self.udpSocketClient.mData = cmdHeader
          
          self.udpSocketClient.sendData()
       
    def sendCmdTriggerType(self): 
        type = mainWindow.getTiggerType()
        type = type << 2
        regAddr= 0x2 # 0x2, Bit[2], 0: Auot, 1: External
        regValue=type
        self.sendCmdWRREG(regAddr,  regValue)
        
    def receiveCmdTriggerType(self): 
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        mainWindow.udpSocketClient.receiveData() # Do nothing
    
    def sendCmdSampleRate(self): 
        sampleRate = mainWindow.getSampleRate()
        type = type << 2
        regAddr= 0x2 # 0x2, Bit[2], 0: Auot, 1: External
        regValue=type
        self.sendCmdWRREG(regAddr,  regValue)
        
    def receiveCmdSampleRate(self): 
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        mainWindow.udpSocketClient.receiveData() # Do nothing

    def sendCmdRecordLength(self): 
#        recordLen = self.getRecordLength()
#        if (recordLen <= 2**16):
#            regAddr= 0x4 # 0x4, Bit[15:0], 0: Auot, 1: External
#            regValue=recordLen * 1024
#            self.sendCmdWRREG(regAddr,  regValue)
#        else:
#            regAddr= 0x4 # 0x4, Bit[15:0], 0: Auot, 1: External
#            regValue=recordLen
#            self.sendCmdWRREG(regAddr,  regValue)
#            regAddr= 0x6 # 0x4, Bit[3:0], High 4 bit
#            regValue=recordLen
#            self.sendCmdWRREG(regAddr,  regValue)
        
            regAddr= 0x4 # 0x4, Bit[15:0], 0: Auot, 1: External
            regValue=1024
            self.sendCmdWRREG(regAddr,  regValue)
            
            self.receiveCmdRecordLength()
            
            regAddr= 0x8 # 0x4, Bit[3:0], High 4 bit
            regValue=1024
            self.sendCmdWRREG(regAddr,  regValue)
            self.receiveCmdRecordLength()
            
        
    def receiveCmdRecordLength(self): 
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        self.udpSocketClient.receiveData() # Do nothing
   
    def sendCmdRAW_AD_SAMPLE(self):
        #print (sys._getframe().f_code.co_name)        
        global gSocketBodySize
        gSocketBodySize = 32*1024 #self.getRecordLength()
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        len = 0 #self.getRecordLength()
        self.sendcommand(0x5a04,0x0000,0x5a04,len,0x0000,0x0000,0x00,0x00,0x0000, None)
          
    def receiveCmdRAW_AD_SAMPLE(self):
#        global gSocketBodySize
#        gSocketBodySize = self.getRecordLength()
#        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        mainWindow.udpSocketClient.receiveData()
        
    
    def sendCmdWRREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', regAddress) +  struct.pack('L', regValue)
        self.sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        
    def sendCmdRDREG(self,  regAddress,  regValue):
        #print (sys._getframe().f_code.co_name)
        global gSocketBodySize
        gSocketBodySize = 8
        self.udpSocketClient.setBufSize(gSocketBodySize + gSocketHeaderSize)
        cmdData  =  struct.pack('L', regAddress) +  struct.pack('L', regValue)
        self.sendcommand(0x5a01,0x0000,0x5a01,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    
    def getTriggerType(self):
        index = mainWindow.comboBox_TriggerDomain.currentIndex()
        return int(index)
        
    def getSampleRate(self):
        sampleRate= 500*1e6
        sampleRateStr = mainWindow.lineEdit_SampleRate.text();
        if (('-' )  == sampleRateStr or "" == sampleRateStr):
            sampleRate = 500*1e6
        else:
            sampleRate = int(sampleRateStr)*1e6 
                
        return sampleRate
        
    
    def getRecordLength(self):
        len = 4
        lenStr = self.lineEdit_RecordLength.text()
        if (('-' )  == lenStr or "" == lenStr):
            len = 4
        else:
            len = int(lenStr)
        return len
        
    def getVoltageScale(self):
        volScale = 200
        volScaleStr = self.lineEdit_VolScale.text()
        volScale = 200
        if (('-' )  == volScaleStr or "" == volScaleStr):
            volScale = 200
        else:
            volScale = int(volScaleStr) 
                
        return volScale
        
    def getOffset(self):
        offset = 0
        offsetStr = self.lineEdit_Offset.text();
        if (('-' )  == offsetStr or "" == offsetStr):
            offset = 0
        else:
            offset = int(offsetStr) 
                
        return offset
        
    
    @pyqtSlot()
    def on_pushButton_Stop_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        self.realTimeThread.stop()
        self.pushButton_Start_TimeDomain.setEnabled(True)
        self.pushButton_Stop_TimeDomain.setEnabled(False)
        self.pushButton_Save_TimeDomain.setEnabled(True)
    
    @pyqtSlot()
    def on_pushButton_Start_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        
        
        
        self.pushButton_Start_TimeDomain.setEnabled(False)
        self.pushButton_Stop_TimeDomain.setEnabled(True)
        self.pushButton_Save_TimeDomain.setEnabled(False)
        self.realTimeThread = RealTimeThread(self.axes, self.canvas, self.radioButton_CHA.isChecked(), 1.0)
        self.realTimeThread.setDaemon(True)
        self.realTimeThread.start()
    
    @pyqtSlot()
    def on_pushButton_Save_TimeDomain_clicked(self):
        """
        Slot documentation goes here.
        """
        # TODO: not implemented yet
        
    @pyqtSlot(int)
    def on_comboBox_TriggerDomain_currentIndexChanged(self, index):
        """
        Slot documentation goes here.
        
        @param index DESCRIPTION
        @type int
        """
        # TODO: not implemented yet
        
        
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())
    

