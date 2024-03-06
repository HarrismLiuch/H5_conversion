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

class H5_Convert_to_Tiff(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("H5 Conversion")
        self.setGeometry(100, 100, 800, 200)

        self.select_folder_btn = QPushButton("Select Folder", self)
        self.select_folder_btn.setGeometry(50, 50, 100, 30)
        self.select_folder_btn.clicked.connect(self.select_folder)

        self.to_folder_btn = QPushButton("To Folder", self)
        self.to_folder_btn.setGeometry(160, 50, 100, 30)
        self.to_folder_btn.clicked.connect(self.to_folder)

        self.convert_btn = QPushButton("Convert", self)
        self.convert_btn.setGeometry(270, 50, 100, 30)
        self.convert_btn.clicked.connect(self.convert)

        self.selected_folder_label = QLabel("Selected Folder: ", self)
        self.selected_folder_label.setGeometry(50, 100, 600, 30)

        self.to_folder_label = QLabel("To Folder: ", self)
        self.to_folder_label.setGeometry(50, 140, 600, 30)
        self.center_window()

    def center_window(self):
        frame_geometry = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        self.selected_folder_label.setText(f"Selected Folder: {folder_path}")

    def to_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "To Folder")
        self.to_folder_label.setText(f"To Folder: {folder_path}")

    def convert(self):
        selected_folder = self.selected_folder_label.text().split(": ")[1]
        to_folder = self.to_folder_label.text().split(": ")[1]
        print(selected_folder, to_folder)
        if selected_folder == "Selected Folder: " or to_folder == "To Folder: ":
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
                        # generate tiffs
                        name = file.split('\\')[-1]
                        print(to_folder + "/" + name + '.tif')
                        try:
                            plt.imsave(to_folder + "/" + name + '.tif', data, format='tiff', cmap=plt.cm.gray)
                        except:
                            makedirs(to_folder, exist_ok=True)
                            plt.imsave(to_folder + "/" +name + '.tif', data, format='tiff', cmap=plt.cm.gray)
                QMessageBox.information(self, "Information", "Conversion completed")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = H5_Convert_to_Tiff()
    widget.show()
    sys.exit(app.exec_())