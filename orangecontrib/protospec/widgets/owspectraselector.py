from AnyQt.QtCore import Qt, pyqtSignal
from AnyQt.QtWidgets import (
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QComboBox,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QHeaderView,
    QSplitter,
)
from orangewidget.utils.visual_settings_dlg import VisualSettingsDialog
import Orange.data
from Orange.widgets.widget import OWWidget, Msg, OWComponent, Input, Output
from Orange.widgets.settings import (
    DomainContextHandler,
    SettingProvider,
    Setting,
)
from orangecontrib.spectroscopy.widgets.utils import (
    SelectionOutputsMixin,
)
from orangecontrib.spectroscopy.widgets.owspectra import SELECTMANY, CurvePlot

class MetaTable(QWidget, OWComponent):

    sigSelectionChanged = pyqtSignal()

    def __init__(self, parent: OWWidget):
        QWidget.__init__(self)
        OWComponent.__init__(self, parent)

        self.data = None

        self.mainArea = QVBoxLayout(self)

        self.filter_widget = QWidget()
        self.filter_layout = QHBoxLayout(self.filter_widget)

        # Combo box to select which column to filter
        self.filter_column = QComboBox()
        self.filter_column.addItem("All Columns")
        self.filter_column.currentIndexChanged.connect(self.filter_table)
        self.filter_layout.addWidget(self.filter_column)

        # Line edit to enter filter value
        self.filter_value = QLineEdit()
        self.filter_value.setPlaceholderText("Enter filter value")
        self.filter_value.textChanged.connect(self.filter_table)
        self.filter_layout.addWidget(self.filter_value)

        # Button to change the selection of all filtered rows
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_visible_rows)
        self.filter_layout.addWidget(self.select_all_btn)

        self.mainArea.addWidget(self.filter_widget)

        # Table widget
        self.table = QTableWidget(self)
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.table.itemChanged.connect(self.on_item_changed)
        self.mainArea.addWidget(self.table)

    def set_data(self, input_data):
        if input_data is None:
            return
        self.data = input_data
        shape = input_data.metas.shape
        self.table.setRowCount(shape[0])
        self.table.setColumnCount(shape[1] + 1)

        # set checkboxes
        for row in range(shape[0]):
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, item)

        # set data
        for row in range(shape[0]):
            for col in range(shape[1]):
                item = QTableWidgetItem(str(input_data.metas[row][col]))
                self.table.setItem(row, col + 1, item)

        self.table.setHorizontalHeaderLabels(
            ["Select"] + [m.name for m in input_data.domain.metas]
        )
        self.filter_column.addItems([m.name for m in input_data.domain.metas])

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def on_item_changed(self, item):
        """Emit signal when an item's checkState changes"""
        if item.column() == 0:  # Checkboxes are in the first column
            self.sigSelectionChanged.emit()

    @property
    def selected_rows(self):
        selected_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_rows.append(row)
        return selected_rows

    def filter_table(self):
        filter_text = self.filter_value.text().lower()
        col_name = self.filter_column.currentText()

        if col_name == "All Columns":
            for row in range(self.table.rowCount()):
                match = False
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item and filter_text in item.text().lower():
                        match = True
                        break
                self.table.setRowHidden(row, not match)
        else:
            col_idx = (
                self.filter_column.currentIndex() - 1
            )  # Adjust for "All Columns" option
            for row in range(self.table.rowCount()):
                item = self.table.item(row, col_idx)
                match = item and filter_text in item.text().lower()
                self.table.setRowHidden(row, not match)

    def select_all_visible_rows(self):
        """Select all visible rows in the table."""
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):  # Only select rows that are not hidden
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)

class OWSpectraSelector(OWWidget):
    name = "Spectra Selector"

    class Inputs:
        data = Input("Data", Orange.data.Table, default=True)

    class Outputs:
        selected_data = Output("Selection", Orange.data.Table, default=True)

    icon = "icons/spectra.svg"

    priority = 11
    keywords = ["curves", "lines", "spectrum"]

    want_control_area = False

    settings_version = 5
    settingsHandler = DomainContextHandler()

    curveplot = SettingProvider(CurvePlot)

    graph_name = "curveplot.plotview"

    class Information(SelectionOutputsMixin.Information):
        showing_sample = Msg("Showing {} of {} curves.")
        view_locked = Msg("Axes are locked in the visual settings dialog.")

    class Warning(OWWidget.Warning):
        no_x = Msg("No continuous features in input data.")

    def __init__(self):
        super().__init__()
        self.settingsAboutToBePacked.connect(self.prepare_special_settings)
        self.curveplot = CurvePlot(self, select=SELECTMANY)
        self.curveplot.locked_axes_changed.connect(
            lambda locked: self.Information.view_locked(shown=locked)
        )
        self.mainArea.layout().addWidget(self.curveplot)

        splitter = QSplitter(self.mainArea)
        splitter.setOrientation(Qt.Vertical)

        # Create a widget to hold the button and table
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)

        # Add table widget to the layout
        self.meta_table = MetaTable(self)
        container_layout.addWidget(self.meta_table)

        # Add the container widget to the splitter
        splitter.addWidget(container_widget)

        # Add the splitter to the main layout
        self.mainArea.layout().addWidget(splitter)

        # Set fixed height for the table
        self.meta_table.setFixedHeight(200)
        self.resize(900, 700)

        # Connect the meta_table signal to update curveplot
        self.meta_table.sigSelectionChanged.connect(self.update_curveplot_data)
        VisualSettingsDialog(self, self.curveplot.parameter_setter.initial_settings)

    def update_curveplot_data(self):
        """Update the curveplot based on the selected rows in the meta_table."""
        selected_rows = self.meta_table.selected_rows
        if self.input_data is not None and selected_rows:
            # Extract the filtered data from the input_data based on selected rows
            selected_data = self.input_data[
                selected_rows, :
            ]  # Assuming self.input_data is an Orange.data.Table
            self.curveplot.set_data(
                selected_data, auto_update=True
            )  # Update the curveplot with new data
            self.curveplot.update_view()  # Update the view to show the new data
            # submitting selection to the output
            self.send_selection(selected_data)
        else:
            # If no rows are selected, clear the plot
            self.curveplot.clear_graph()  # You may need a method to clear the plot

    def send_selection(self, selected_data):
        self.Outputs.selected_data.send(selected_data)

    @Inputs.data
    def set_data(self, input_data):
        self.closeContext()
        self._showing_sample_info(None)
        self.Warning.no_x.clear()
        self.openContext(input_data)

        self.input_data = input_data  # Store input data for later use
        self.update_curveplot_data()  # Update curveplot data based on current selection
        # update tabled_data with data metas
        self.meta_table.set_data(input_data)

    def set_visual_settings(self, key, value):
        self.curveplot.parameter_setter.set_parameter(key, value)

    def handleNewSignals(self):
        self.curveplot.update_view()

    def _showing_sample_info(self, num):
        if num is not None and self.curveplot.data and num != len(self.curveplot.data):
            self.Information.showing_sample(num, len(self.curveplot.data))
        else:
            self.Information.showing_sample.clear()

    def save_graph(self):
        # directly call save_graph so it hides axes
        self.curveplot.save_graph()

    def prepare_special_settings(self):
        self.curveplot.save_peak_labels()

    def onDeleteWidget(self):
        self.curveplot.shutdown()
        super().onDeleteWidget()


if __name__ == "__main__":  # pragma: no cover
    from Orange.widgets.utils.widgetpreview import WidgetPreview
    from orangecontrib.spectroscopy.io.neaspec import NeaReaderGSF
    from Orange.data.io import FileFormat
    from Orange.data import dataset_dirs

    fn = "NeaReaderGSF_test/NeaReaderGSF_test O2P raw.gsf"
    absolute_filename = FileFormat.locate(fn, dataset_dirs)
    data = NeaReaderGSF(absolute_filename).read()
    WidgetPreview(OWSpectraSelector).run(set_data=data)
