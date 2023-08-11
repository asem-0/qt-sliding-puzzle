import sys
from datetime import datetime
from random import randint
from time import sleep

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

class Tile(QLabel):
    """
    Custom class of a label that can be clicked. It does so by catching the
    mousePressEvent then emitting that in clicked Signal.
    """

    # Signal to be emitted when the label is clicked
    clicked = Signal()  # for short click

    def __init__(self, location, fraction):
        """Initialize the tile."""
        # Initialize the parent class
        super().__init__()
        self._location = location  # Current location of the tile
        self._id = location  # id of the tile (correct location)
        self.fraction = fraction  # The image fraction to be displayed
        self.current_alpha = 255  # Initial alpha value
        self.fade_step = 50  # How much to change the alpha value by for fading

        # Timers for fading in and out
        self.fade_out_timer = QTimer(self)
        self.fade_out_timer.timeout.connect(self.fade_out)
        self.fade_in_timer = QTimer(self)
        self.fade_in_timer.timeout.connect(self.fade_in)

        # How long to wait between each step of the fade
        self.fade_step_duration = 1

    def mousePressEvent(self, event):
        """A default qt function that is called when a mouse press event occurs, but
        we override it to emit the clicked signal."""
        # Check if the left button is pressed
        if event.button() == Qt.LeftButton:
            # If it is then we emit the clicked signal
            self.clicked.emit()

    def is_in_right_place(self):
        """Check if the tile is in the right place by comparing current location with id."""
        return self._location == self._id

    def paintEvent(self, event):
        """Override the paint event to draw the pixmap with the current alpha value."""
        painter = QPainter(self)
        painter.setOpacity(self.current_alpha / 255)  # Set opacity based on alpha
        painter.drawPixmap(0, 0, self.fraction)

    def fade_out(self):
        """Fade out the tile by decreasing the alpha value."""
        # Check if the timer is active if not start it
        if not self.fade_out_timer.isActive():
            self.fade_out_timer.start(self.fade_step_duration)
        # Check if the alpha value is greater than 0
        if self.current_alpha > 0:
            # Decrease the alpha value
            self.current_alpha -= self.fade_step
            self.update()  # Trigger a repaint to show the updated alpha
        else:
            # Stop the timer if the alpha value is less than 0
            self.fade_out_timer.stop()

    def fade_in(self):
        """Fade in the tile by increasing the alpha value."""
        # Check if the timer is active if not start it
        if not self.fade_in_timer.isActive():
            self.fade_in_timer.start(self.fade_step_duration)
        # Check if the alpha value is less than 255
        if self.current_alpha < 255:
            # Increase the alpha value
            self.current_alpha += self.fade_step
            self.update()
        else:
            # Stop the timer if the alpha value is greater than 255
            self.fade_in_timer.stop()

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, location):
        self._location = location

    @property
    def id(self):
        return self._id


class Gameboard(QWidget):
    """The gameboard widget"""

    won_signal = Signal()

    def __init__(self, window_height):
        super().__init__()

        self.counter = 0  # step counter
        self.game_running = False  # game state
        self.grid_size = 3  # grid size
        self.window_height = window_height

        self.current_empty_tile = None  # current empty tile
        self.image = None  # holder of the pixmap image
        self.image_label = None  # holder of the whole image label
        self.image_fraction = {}  # image fractions
        self.tiles = {}  # holder for tiles
        self.file_path = None  # file path of the image

        # set up the game grid
        self.gamegrid = QGridLayout()
        self.setLayout(self.gamegrid)

    def get_moveable_tiles(self):
        """Returns a list of tiles that can be moved"""
        moveable_tiles = []
        # Loop through the grid
        for col in range(self.grid_size):
            for row in range(self.grid_size):
                # Check if the tile can be moved
                if self.moveable_tile((row, col)):
                    moveable_tiles.append((row, col))
        return moveable_tiles

    def reset_holders(self):
        """Function used to reset the different holders.
        Used when a new image is loaded or a new game is started.
        Also used when the game is won."""

        # reset the holders
        self.current_empty_tile = (self.grid_size - 1, self.grid_size - 1)
        self.image_fraction = {}
        try:
            # delete the image label from the memory ### important
            self.image_label.deleteLater()
            self.image_label = None
        except (RuntimeError, AttributeError):
            # if the image label is not in the memory then pass
            pass

        # reset the tiles
        for col in range(self.grid_size):
            for row in range(self.grid_size):
                if self.gamegrid.itemAtPosition(row, col):
                    self.gamegrid.removeItem(self.gamegrid.itemAtPosition(row, col))
                    try:
                        # delete the tile from the memory ### important
                        self.tiles[(row, col)].deleteLater()
                    except KeyError:
                        pass
        self.tiles = {}

    def tile_clicked(self):
        """Slot function for when a tile is clicked"""
        # Check if the game is running
        if not self.game_running:
            return
        # Get the tile that was clicked
        tile = self.sender()
        # Check if the tile can be moved
        if self.moveable_tile(tile.location):
            # Move the tile
            self.move_tile(tile, "fade")
            # Check if the game is won
            if self.check_win():
                # Set the game to won state
                self.set_won_state()

    def set_won_state(self, emit=True):
        """Function used to set the game to won state"""
        # Emit the won signal if emit is True
        if emit:
            self.won_signal.emit()

        # Clear the tiles to show the whole image
        self.reset_holders()

        # Set up the whole image and show it
        self.image_label = QLabel()
        self.image_label.setPixmap(self.image)
        self.image_label.resize(self.image.width(), self.image.height())
        self.gamegrid.addWidget(self.image_label, 0, 0)

        # Set the game to not running and reset the counter
        self.game_running = False
        self.counter = 0

    def shuffle(self, grid_size):
        """Shuffles the tiles"""
        # Check if the game is running
        if self.game_running:
            # if it is running then the game is reset
            # this triggered when the user clicks stop the game so the game is reset
            # by switching to won state then returning
            self.set_won_state(False)
            return

        # Set the grid size
        self.grid_size = grid_size

        # Remove the whole image label from the grid
        self.gamegrid.removeItem(self.gamegrid.itemAtPosition(0, 0))
        self.image_label.deleteLater()  # delete the image label from the memory ### important

        # Calculate the tile width and height based on the grid size
        tile_width = self.image.height() / self.grid_size
        tile_height = self.image.height() / self.grid_size

        # Set up the tiles
        self.image_fraction = {}
        for col in range(self.grid_size):
            for row in range(self.grid_size):
                self.image_fraction[(row, col)] = self.image.copy(
                    col * tile_width, row * tile_height, tile_width, tile_height
                )
                self.tiles[(row, col)] = Tile(
                    (row, col), self.image_fraction[(row, col)]
                )
                self.tiles[(row, col)].setPixmap(self.image_fraction[(row, col)])
                self.gamegrid.addWidget(self.tiles[(row, col)], row, col, 1, 1)
                self.tiles[(row, col)].clicked.connect(self.tile_clicked)

        # Remove the last tile
        self.gamegrid.removeItem(
            self.gamegrid.itemAtPosition(self.grid_size - 1, self.grid_size - 1)
        )
        self.current_empty_tile = (self.grid_size - 1, self.grid_size - 1)
        self.tiles[self.current_empty_tile].deleteLater()  # Also from memory

        # Finally we shuffle the tiles by making random moves
        while True:
            # We make grid_size**2 random moves
            for _ in range(self.grid_size**2):
                # Get the moveable tiles
                neightbors = self.get_neightbor_tiles(self.current_empty_tile)
                # Pick a random tile
                tile = self.tiles[neightbors[randint(0, len(neightbors) - 1)]]
                # Move the tile
                self.move_tile(tile)

            # Check if the empty tile is in the bottom right corner
            if self.current_empty_tile == (self.grid_size - 1, self.grid_size - 1):
                # Check if the game is not won (in case the shuffle created solved game)
                if not self.check_win():
                    # Stop the shuffling loop
                    break
            # If the game is won or the bottom right corner tile is not empty
            # then we shuffle again until both conditions are met

        # Flag the game as running and reset the counter
        self.game_running = True
        self.counter = 0

    def check_win(self):
        """Checks if the game is won"""
        # Loop through the tiles and check if they are in the right place
        for tile in self.tiles.values():
            # If one tile is not in the right place then the game is not won
            if not tile.is_in_right_place():
                return False
        # If all tiles are in the right place then the game is won
        return True

    def move_tile(self, tile, mode="normal"):
        """Moves the tile to the new location"""
        # Increment the counter
        self.counter += 1

        new_location = self.current_empty_tile
        row, col = new_location

        # Apply the fade out effect if mode is fade
        if mode == "fade":
            tile.fade_out()
            # Wait until the fade out effect is done
            while tile.fade_out_timer.isActive():
                sleep(0.01)
                app.processEvents()
        # Remove the tile from the grid
        self.gamegrid.removeWidget(tile)

        # Update the empty tile inner location
        self.tiles[self.current_empty_tile].location = tile.location

        # Swap the tiles (hidden tile and the tile that was clicked)
        self.tiles[tile.location], self.tiles[new_location] = self.tiles.pop(
            new_location
        ), self.tiles.pop(tile.location)

        # Add the tile to the new location
        self.gamegrid.addWidget(tile, row, col)
        if mode == "fade":
            tile.fade_in()
            # Wait until the fade in effect is done
            while tile.fade_in_timer.isActive():
                sleep(0.01)
                app.processEvents()
        # Swap the locations of the tiles (hidden tile and the tile that was clicked)
        self.current_empty_tile, tile.location = tile.location, new_location

    def tile_is_empty(self, location):
        """Returns true if the tile at the location is empty"""
        row, col = location
        # Nothing on this location on the grid, then it is empty
        if self.gamegrid.itemAtPosition(row, col) is None:
            return True
        return False

    def get_neightbor_tiles(self, location):
        """Returns the neightbor tiles of the tile at the location"""
        row, col = location
        neightbors = []
        # Check if the tile is not in the first row
        if row > 0:
            neightbors.append((row - 1, col))
        # Check if the tile is not in the last row
        if row < self.grid_size - 1:
            neightbors.append((row + 1, col))
        # Check if the tile is not in the first column
        if col > 0:
            neightbors.append((row, col - 1))
        # Check if the tile is not in the last column
        if col < self.grid_size - 1:
            neightbors.append((row, col + 1))
        return neightbors

    def moveable_tile(self, location):
        """Returns true if the tile is moveable, next to the empty tile"""
        return self.current_empty_tile in self.get_neightbor_tiles(location)

    def load_image(self, file_path=None, hint_width=150, hint_image=None):
        """Loads an image from the file path specified in the line edit widget."""
        # If the file path is not specified then we use the one in the line edit widget
        # Otherwise we use the one specified in the function call (new image)
        if file_path is not None:
            self.file_path = file_path

        # Clear previous image and grid
        self.reset_holders()

        # Read image
        if self.file_path:
            self.image = QPixmap(self.file_path)
        if self.image.isNull():
            raise Exception("The image file is not valid")
        # Crop the image to a square
        self.image = self.image.copy(0, 0, self.image.height(), self.image.height())

        # Scale the image to the window height
        self.image = self.image.scaled(
            self.window_height, self.window_height, Qt.KeepAspectRatio
        )

        # Create the large image label and add image to it
        self.image_label = QLabel()
        self.image_label.setPixmap(self.image)
        self.image_label.resize(self.image.width(), self.image.height())
        # Add the image label to the grid
        self.gamegrid.addWidget(self.image_label, 0, 0)

        # Update the image hint to the new image
        self.image_hint = self.image.copy(
            0, 0, self.image.height(), self.image.height()
        )

        # Scale the image hint to the new width
        self.image_hint = self.image_hint.scaled(
            hint_width, hint_width, Qt.KeepAspectRatio
        )
        hint_image.setPixmap(self.image_hint)


class MainWindow(QMainWindow):
    """Main window class, the main window of the application."""

    def __init__(self):
        """Initializes the main window object."""
        super().__init__()
        # Get the application height
        screen_height = app.primaryScreen().availableGeometry().height() - 30

        # Set application title and load configs
        self.setWindowTitle("qt-Sliding Puzzle 0.1")

        # Show and set status bar
        self.statusBar().showMessage("Ready")

        # Set flags and timer
        self.game_running = False
        self.time_ref = None
        self.side_panel_width = 200
        self.timer = QTimer()

        # Set application height
        self.setFixedSize(screen_height + self.side_panel_width, screen_height)

        # Instantiate the gameboard
        self.gameboard = Gameboard(screen_height)

        # Create the application layout
        self.layout_box = QHBoxLayout()

        # Large font
        large_font = QFont()
        large_font.setPointSize(18)

        # Create the side panel
        # Create widgets

        # Create the status label for game status and timer
        self.status_text = QLabel("Pick an image\nto start the game")
        self.status_text.setFixedSize(self.side_panel_width, 95)
        self.status_text.setAlignment(Qt.AlignCenter)
        self.status_text.setStyleSheet(
            "QLabel { background-color : white; color : black; }"
        )
        self.status_text.setFont(large_font)

        # Create the filename label and line edit
        filename_label = QLabel("Image file:")
        filename_label.setFixedSize(self.side_panel_width, 30)
        self.filename = QLineEdit()
        self.filename.setFixedSize(self.side_panel_width, 30)
        self.filename.setReadOnly(True)

        # Create the browse button
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedSize(self.side_panel_width, 30)

        # Create the toggle button to start/stop the game
        self.toggle_button = QPushButton("Start game")
        self.toggle_button.setFixedSize(self.side_panel_width, 30)
        self.toggle_button.setEnabled(False)

        # Create the grid size selection spinner
        spinner_layout = QHBoxLayout()
        spinner_label = QLabel("Grid size:")
        self.spinner = QSpinBox()
        self.spinner.setFixedSize(self.side_panel_width - 100, 30)
        self.spinner.setRange(2, 10)
        self.spinner.setValue(3)
        spinner_layout.addWidget(spinner_label)
        spinner_layout.addWidget(self.spinner)

        # Hint image box
        hint_label = QLabel("Hint:")
        hint_label.setFixedSize(self.side_panel_width, 30)
        self.hint_image = QLabel()
        self.hint_image.setStyleSheet("background-color: grey;")
        self.hint_image.setFixedSize(self.side_panel_width, self.side_panel_width)

        # Side panel layout
        self.buttons_layout = QVBoxLayout()
        self.buttons_layout.addWidget(self.status_text)
        self.buttons_layout.addWidget(filename_label)
        self.buttons_layout.addWidget(self.filename)
        self.buttons_layout.addWidget(self.browse_button)
        self.buttons_layout.addWidget(self.toggle_button)
        self.buttons_layout.addLayout(spinner_layout)
        self.buttons_layout.addWidget(hint_label)
        self.buttons_layout.addWidget(self.hint_image)
        self.buttons_layout.setAlignment(Qt.AlignLeft)

        # Connect signals
        self.browse_button.clicked.connect(self.browse_n_load)
        self.toggle_button.clicked.connect(
            lambda: self.gameboard.shuffle(self.spinner.value())
        )
        self.toggle_button.clicked.connect(self.toggle_game_state)
        self.gameboard.won_signal.connect(self.won_game)
        self.timer.timeout.connect(self.refresh_status)

        # Add widgets to main layout
        self.layout_box.addLayout(self.buttons_layout)
        self.layout_box.addWidget(self.gameboard)
        self.layout_widget = QWidget()
        self.layout_widget.setLayout(self.layout_box)
        self.setCentralWidget(self.layout_widget)
        self.showMaximized()
        self.show()

    def toggle_game_state(self):
        """Starts\stops the timer and sets the game to running."""
        if not self.game_running:
            # Start the timer and update the time reference
            self.time_ref = datetime.now()
            self.timer.start(100)
            self.game_running = True
            # Update the timer text and disable browse button
            self.toggle_button.setText("Stop game")
            self.browse_button.setEnabled(False)
            return

        # Stop the timer and update the status text
        self.timer.stop()
        self.game_running = False
        self.status_text.setText("Game forfeited!")

        # Update the toggle button and enable browse button
        self.toggle_button.setText("Start game")
        self.browse_button.setEnabled(True)

    def won_game(self):
        """Sets the game interface to a won state."""
        # Stop the timer and update the status text
        self.timer.stop()
        self.game_running = False

        # Calculate the game duration and update the timer text
        game_duration = str(datetime.now() - self.time_ref).split(".")[0][2:]
        text_message = (
            f"You won\nTime: {game_duration}\nMoves: {self.gameboard.counter}"
        )
        self.status_text.setText(text_message)

        # Update the toggle button and enable browse button
        self.toggle_button.setText("Start game")
        self.browse_button.setEnabled(True)

    def refresh_status(self):
        """Refreshes the status text and status bar."""
        if self.game_running:
            self.status_text.setText(
                str(datetime.now() - self.time_ref).split(".")[0][2:]
            )
            self.statusBar().showMessage("Moves: " + str(self.gameboard.counter))

    def browse_n_load(self):
        """Opens a file dialog to browse for a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open file", "", "Image files (*.jpg *.png)"
        )
        if file_path:
            # Load the image and update the filename label
            self.filename_path = file_path
            self.filename.setText(file_path.split("/")[-1])
            try:
                self.gameboard.load_image(
                    file_path, self.side_panel_width, self.hint_image
                )
            except Exception as e:
                self.status_text.setText("Error loading\nimage!")
                print(e, type(e))
                return
            self.toggle_button.setEnabled(True)

            # Update the Status text
            self.status_text.setText("Choose grid size\nthen click start")


if __name__ == "__main__":
    sys.argv += ["-platform", "windows:darkmode=2"]
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    sys.exit(app.exec())
