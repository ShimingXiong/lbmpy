from itertools import cycle
import matplotlib.patches as patches

from pystencils import make_slice
from pystencils.plot2d import *


def boundary_handling(boundary_handling_obj, slice_obj=None, boundary_name_to_color=None, show_legend=True):
    """Image plot that shows boundary markers of a 2D domain slice.

    Args:
        boundary_handling_obj: instance of :class:`lbmpy.boundaries.BoundaryHandling`
        slice_obj: for 3D boundary handling a slice expression has to be passed here to define the plane that
                   should be plotted
        boundary_name_to_color: optional dictionary mapping boundary names to colors
        show_legend: if True legend for color->boundary name is added
    """
    from matplotlib.colors import ListedColormap, BoundaryNorm

    boundary_handling_obj.prepare()

    dh = boundary_handling_obj.data_handling
    flag_arr = dh.gather_array(boundary_handling_obj.flag_array_name, slice_obj, ghost_layers=True).squeeze()
    if flag_arr is None:
        return

    if len(flag_arr.shape) != 2 and slice_obj is None:
        raise ValueError("To plot a 3D boundary handling a slice has to be passed")

    if boundary_name_to_color:
        fixed_colors = boundary_name_to_color
    else:
        fixed_colors = {
            'fluid': '#56b4e9',
            'NoSlip': '#999999',
            'UBB': '#d55e00',
            'FixedDensity': '#009e73',
        }

    boundary_names = []
    flag_values = []
    for boundary_obj in boundary_handling_obj.boundary_objects:
        boundary_names.append(boundary_obj.name)
        flag_values.append(boundary_handling_obj.get_flag(boundary_obj))

    default_cycle = matplotlib.rcParams['axes.prop_cycle']
    color_values = [fixed_colors[name] if name in fixed_colors else c['color']
                    for c, name in zip(default_cycle, boundary_names)]

    colormap = ListedColormap(color_values)
    bounds = np.array(flag_values, dtype=float) - 0.5
    bounds = list(bounds) + [bounds[-1] + 1]
    norm = BoundaryNorm(bounds, colormap.N)

    flag_arr = flag_arr.swapaxes(0, 1)
    imshow(flag_arr, interpolation='none', origin='lower',
           cmap=colormap, norm=norm)

    path_list = [matplotlib.patches.Patch(color=color, label=name) for color, name in zip(color_values, boundary_names)]
    axis('equal')
    if show_legend:
        legend(handles=path_list, bbox_to_anchor=(1.02, 0.5), loc=2, borderaxespad=0.)


def phase_plot(phase_field: np.ndarray, linewidth=1.0, clip=True) -> None:
    """Plots a phase field array using the phase variables as alpha channel.

    Args:
        phase_field: array with len(shape) == 3, first two dimensions are spatial, the last one indexes the phase
                     components.
        linewidth: line width of the 0.5 contour lines that are drawn over the alpha blended phase images
        clip: see scalar_field_alpha_value function
    """
    color_cycle = cycle(['#fe0002', '#00fe00', '#0000ff', '#ffa800', '#f600ff'])

    assert len(phase_field.shape) == 3

    for i in range(phase_field.shape[-1]):
        scalar_field_alpha_value(phase_field[..., i], next(color_cycle), clip=clip, interpolation='bilinear')
    if linewidth:
        for i in range(phase_field.shape[-1]):
            scalar_field_contour(phase_field[..., i], levels=[0.5], colors='k', linewidths=[linewidth])


def phase_plot_for_step(phase_field_step, slice_obj=make_slice[:, :], **kwargs):
    concentrations = phase_field_step.concentration[slice_obj]
    phase_plot(concentrations, **kwargs)


class LbGrid:
    """Visualizes a 2D LBM grid with matplotlib by drawing cells and pdf arrows"""

    def __init__(self, x_cells, y_cells):
        """Create a new grid with the given number of cells in x (horizontal) and y (vertical) direction"""

        self._xCells = x_cells
        self._yCells = y_cells

        self._patches = []
        for x in range(x_cells):
            for y in range(y_cells):
                self._patches.append(patches.Rectangle((x, y), 1.0, 1.0, fill=False, linewidth=3, color='#bbbbbb'))

        self._cellBoundaries = dict()  # mapping cell to rectangle patch
        self._arrows = dict()  # mapping (cell, direction) tuples to arrow patches

    def add_cell_boundary(self, cell, **kwargs):
        """Draws a rectangle around a single cell. Keyword arguments are passed to the matplotlib Rectangle patch"""
        kwargs.setdefault('fill', False)
        kwargs.setdefault('linewidth', 3)
        kwargs.setdefault('color', '#bbbbbb')
        self._cellBoundaries[cell] = patches.Rectangle(cell, 1.0, 1.0, **kwargs)

    def add_cell_boundaries(self, **kwargs):
        """Draws a rectangle around all cells. Keyword arguments are passed to the matplotlib Rectangle patch"""
        for x in range(self._xCells):
            for y in range(self._yCells):
                self.add_cell_boundary((x, y), **kwargs)

    def add_arrow(self, cell, arrow_position, arrow_direction, **kwargs):
        """
        Draws an arrow in a cell. If an arrow exists already at this position, it is replaced.

        :param cell: cell coordinate as tuple (x,y)
        :param arrow_position: each cell has 9 possible positions specified as tuple e.g. upper left (-1, 1)
        :param arrow_direction: direction of the arrow as (x,y) tuple
        :param kwargs: arguments passed directly to the FancyArrow patch of matplotlib
        """
        cell_midpoint = (0.5 + cell[0], 0.5 + cell[1])

        kwargs.setdefault('width', 0.005)
        kwargs.setdefault('color', 'k')

        if arrow_position == (0, 0):
            del kwargs['width']
            self._arrows[(cell, arrow_position)] = patches.Circle(cell_midpoint, radius=0.03, **kwargs)
        else:
            arrow_midpoint = (cell_midpoint[0] + arrow_position[0] * 0.25,
                              cell_midpoint[1] + arrow_position[1] * 0.25)
            length = 0.75
            arrow_start = (arrow_midpoint[0] - arrow_direction[0] * 0.25 * length,
                           arrow_midpoint[1] - arrow_direction[1] * 0.25 * length)

            patch = patches.FancyArrow(arrow_start[0], arrow_start[1],
                                       0.25 * length * arrow_direction[0],
                                       0.25 * length * arrow_direction[1],
                                       **kwargs)
            self._arrows[(cell, arrow_position)] = patch

    def fill_with_default_arrows(self, **kwargs):
        """Fills the complete grid with the default pdf arrows"""
        for x in range(self._xCells):
            for y in range(self._yCells):
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        kwargs.setdefault('color', '#bbbbbb')
                        kwargs.setdefault('width', 0.066)

                        self.add_arrow((x, y), (dx, dy), (dx, dy), **kwargs)

    def draw(self, ax):
        """Draw the grid into a given matplotlib axes object"""

        for p in self._patches:
            ax.add_patch(p)

        for arrow_patch in self._arrows.values():
            ax.add_patch(arrow_patch)

        offset = 0.1
        ax.set_xlim(-offset, self._xCells+offset)
        ax.set_xlim(-offset, self._xCells + offset)
        ax.set_ylim(-offset, self._yCells + offset)
        ax.set_aspect('equal')
        ax.set_axis_off()
