import sys

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel

from PyQt5.QtWidgets import QDesktopWidget
from os import makedirs
import glob
from PyQt5.QtWidgets import QMessageBox
import numpy as np
import h5py
import hdf5plugin
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtGui import QDoubleValidator

class H5_Convert_to_Tiff(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("H5 Conversion")
        self.setGeometry(100, 100, 1200, 300)

        self.select_folder_btn = QPushButton("Select Folder", self)
        self.select_folder_btn.setGeometry(50, 50, 150, 50)
        self.select_folder_btn.clicked.connect(self.select_folder)

        self.to_folder_btn = QPushButton("To Folder", self)
        self.to_folder_btn.setGeometry(200, 50, 150, 50)
        self.to_folder_btn.clicked.connect(self.to_folder)

        self.convert_btn = QPushButton("Convert to .tif/.npy/.tiff", self)
        self.convert_btn.setGeometry(350, 50, 250, 50)
        self.convert_btn.clicked.connect(self.convert_tif)

        self.selected_folder_label = QLabel("Selected Folder: ", self)
        self.selected_folder_label.setGeometry(50, 100, 600, 50)

        self.to_folder_label = QLabel("To Folder: ", self)
        self.to_folder_label.setGeometry(50, 140, 600, 50)

        self.max_threshold_label = QLabel("Max Threshold %:", self)
        self.max_threshold_label.setGeometry(700, 0, 150, 30)

        self.max_threshold_input = QLineEdit(self)
        self.max_threshold_input.setGeometry(850, 0, 100, 30)
        self.max_threshold_input.setValidator(QDoubleValidator(0, 100, 2))

        self.min_threshold_label = QLabel("Min Threshold %:", self)
        self.min_threshold_label.setGeometry(700, 50, 150, 30)  
        
        self.min_threshold_input = QLineEdit(self)
        self.min_threshold_input.setGeometry(850, 50, 100, 30)
        self.min_threshold_input.setValidator(QDoubleValidator(0, 100, 2))

        self.select_flatfield_file_btn = QPushButton("Select Flatfield File", self)
        self.select_flatfield_file_btn.setGeometry(50, 200, 150, 50)
        self.select_flatfield_file_btn.clicked.connect(self.select_flatfield_file)

        '''...

        def convert_tif(self):
            selected_folder = self.selected_folder_label.text().split(": ")[1]
            to_folder = self.to_folder_label.text().split(": ")[1]
            max_threshold = float(self.max_threshold_input.text())
            print(selected_folder, to_folder, max_threshold)
            ...'''


        self.center_window()

    def center_window(self):
        frame_geometry = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def select_flatfield_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Flatfield File", "", "Numpy Files (*.npy);;All Files (*)")
        if file_path:
            try:
                self.flatfield = np.load(file_path)
                if self.flatfield.shape != (512, 512):
                    QMessageBox.warning(self, "Warning", "Flatfield file must be of shape (512, 512)")
                    self.flatfield = None
                else:
                    QMessageBox.information(self, "Information", f"Flatfield file {file_path} loaded successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load flatfield file: {e}")
                self.flatfield = None
        else:
            self.flatfield = None

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder_label.setText(f"Selected Folder: {folder_path}")

    def to_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "To Folder")
        self.to_folder_label.setText(f"To Folder: {folder_path}")

    def convert_tif(self):
        selected_folder = self.selected_folder_label.text().split(": ")[1]
        to_folder = self.to_folder_label.text().split(": ")[1]
        if self.max_threshold_input.text() == "" or self.min_threshold_input.text() == "":
            QMessageBox.warning(self, "Warning", "Please enter the max and min threshold")
        else:
            max_threshold = float(self.max_threshold_input.text())
            min_threshold = float(self.min_threshold_input.text())
            print(selected_folder, to_folder, max_threshold, min_threshold)
            if max_threshold < 0 or max_threshold > 100 or min_threshold < 0 or min_threshold > 100:
                QMessageBox.warning(self, "Warning", "Please enter the max and min threshold between 0 and 100")
            elif max_threshold <= min_threshold:
                QMessageBox.warning(self, "Warning", "Max threshold should be greater than min threshold")
            else:
                if selected_folder == "" or to_folder == "":
                    QMessageBox.warning(self, "Warning", "Please select the folder and to folder")
                else:
                    h5_files = glob.glob(selected_folder + "/*.h5")
                    # Find the file with keyword
                    keyword = 'master'
                    # Remove the file extension
                    h5_files = [file.rstrip('.h5') for file in h5_files if keyword in file]
                    if len(h5_files) == 0:
                        QMessageBox.warning(self, "Warning", "No H5 files found in the selected folder")
                    else:
                        for file in h5_files:
                            with h5py.File(file + '.h5', 'r') as f:
                                #print(f['entry/data/data'].keys())
                
                                # Load data
                                dataset = f['entry/data/data_000001']
                                # Read the dataset into a NumPy array
                                data = np.array(dataset)
                                # For images with dead pixels
                                #data[data == 4294967295] = 0
                                data = data.reshape(512, 512)
                                # remove the crosshair using a flatfield correction
                                r_crosshair = 0.8886
                                data[254:258, :] = data[254:258, :]/r_crosshair
                                data[:, 254:258] = data[:, 254:258]/r_crosshair
                                # remove dead pixels
                                data[164, 87] = (data[163, 87] + data[165, 87] + data[164, 86] + data[164, 88])/4
                                data[192,85] = (data[191, 85] + data[193, 85] + data[192, 84] + data[192, 86])/4
                                # define name
                                name = file.split('\\')[-1]
                                # save npy file
                                try:
                                    np.save(to_folder + "/" + name + '.npy', data)
                                except:
                                    makedirs(to_folder, exist_ok=True)
                                    np.save(to_folder + "/" + name + '.npy', data)
                                # print the path
                                print(to_folder + "/" + name + '.npy')
                                # apply threshold
                                max_threshold_val = np.percentile(data, max_threshold)
                                data[data > max_threshold_val] = max_threshold_val
                                min_threshold_val = np.percentile(data, min_threshold)
                                data[data < min_threshold_val] = min_threshold_val
                                # generate tiffs
                                try:
                                    plt.imsave(to_folder + "/" + name + '.tif', data, format='tiff', cmap=plt.cm.gray)
                                except:
                                    makedirs(to_folder, exist_ok=True)
                                    plt.imsave(to_folder + "/" +name + '.tif', data, format='tiff', cmap=plt.cm.gray)
                                # print the path
                                print(to_folder + "/" + name + '.tif')
                        QMessageBox.information(self, "Information", "Conversion completed")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = H5_Convert_to_Tiff()
    widget.show()
    sys.exit(app.exec_())