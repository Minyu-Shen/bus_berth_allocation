import numpy as np
import itertools
# from shapely.geometry import Point
# from shapely.geometry.polygon import Polygon, LineString
from arena import uniform_sample_from_unit_simplex
from sim_results import get_delay_of_continuous
from operator import attrgetter
import matplotlib.pyplot as plt
from collections import defaultdict
import numpy.linalg as LA


class Region(object):
    def __init__(self, region_id, dim, vertexs, depth):
        self.region_id = region_id
        self.dim = dim
        self.vertexs = vertexs  # a list of coordinates
        self.depth = depth
        self.distance_to_center = self.cal_distance_to_center()

        self.children = []
        self.parent = None

        # store pre-sample data
        self.pre_sample_points = []
        self.pre_sample_size = 400

    def evaluate_children_return_best(
        self,
        sample_num_of_each_region,
        line_flow,
        line_service,
        opt_stats,
        run_df=None,
        sim_info=None,
    ):
        child_region_sample_delays_dict = defaultdict(list)
        for child_region in self.children:
            for _ in range(sample_num_of_each_region):
                assign_plan, delay = self.sample_one_plan(
                    line_flow, line_service, run_df, sim_info
                )
                opt_stats.add_eval_info(assign_plan, delay)
                child_region_sample_delays_dict[child_region.region_id].append(delay)
        best_child_region_tuple = min(
            child_region_sample_delays_dict.items(), key=lambda x: min(x[1])
        )
        return best_child_region_tuple

    def cal_distance_to_center(self):
        distance = 0.0
        center = np.array([1.0 / self.dim] * self.dim)
        for vertex in self.vertexs:
            vertex_array = np.array(vertex)
            error = ((vertex_array - center) ** 2).mean()
            distance += error
        return distance

    def is_pre_sample_enough(self):
        return True if len(self.pre_sample_points) >= self.pre_sample_size else False

    def sample_one_plan(self, line_flow, line_service, run_df=None, sim_info=None):
        while True:
            continuous_vector = self.pre_sample_points.pop()
            assign_plan, delay = get_delay_of_continuous(
                line_flow, line_service, continuous_vector, run_df, sim_info
            )
            # print("evaluated one plan's delay:", delay)
            if assign_plan is not None:
                return assign_plan, delay

    def dispatch_point_to_children(self):
        if len(self.children) != 0:
            dspt_num = len(self.pre_sample_points) - 400  # keep 200 for self
            for _ in range(dspt_num):
                point = self.pre_sample_points.pop()
                ### get the region with min distance
                child_dist_sum_dict = {r: 0.0 for r in self.children}

                for r in self.children:
                    center = [0] * self.dim
                    for each_vertex in r.vertexs:
                        for each_dim in range(self.dim):
                            center[each_dim] += each_vertex[each_dim]
                    center = [x / self.dim for x in center]
                    to_center_dist_sum = 0.0
                    for d in range(self.dim):
                        to_center_dist_sum += abs(center[d] - point[d])
                        child_dist_sum_dict[r] = to_center_dist_sum

                    # surr_sum = 0.0
                    # for each_vertex in r.vertexs:
                    #     for d in range(self.dim):
                    #         surr_sum += abs(each_vertex[d] - point[d])
                    # child_dist_sum_dict[r] = surr_sum

                min_region = min(child_dist_sum_dict, key=child_dist_sum_dict.get)
                min_region.pre_sample_points.append(point)

    def add_pre_sample_point(self, point):
        """ add pre-sampled point into property
        point -- a tuple of point
        """
        if self.is_point_in_region(point):
            self.pre_sample_points.append(point)

            # return True
        # else:
        # return False

    def is_point_in_region(self, point, by="distance"):
        """ 
        point -- a tuple of point
        """
        assert len(point) == self.dim, "dimension is mismatched"
        A = [list(v) for v in self.vertexs]
        A = np.array(A).T
        b = np.array(point)
        coefs = LA.solve(A, b)
        return True if (coefs >= 0).all() else False

        ### unused, for c<=3 only
        # if self.dim == 2:  # construct a line
        #     p_point = Point(point)
        #     line = LineString(self.vertexs)
        #     assert line.is_valid, "line defined by self.vertexs should be valid"
        #     return True if line.contains(p_point) else False
        # elif self.dim == 3:  # construct a polygon
        #     p_point = Point(point)
        #     polygon = Polygon(self.vertexs)
        #     assert polygon.is_valid, "polygon defined by self.vertexs should be valid"
        #     return True if polygon.contains(p_point) else False
        # else:  # based on distance
        #     if self.region_id == 0:  # the root region
        #         return True
        #     else:
        #         # return True
        #         all_regions_same_depth = self.parent.children
        #         surr_sum_dict = {r.region_id: 0.0 for r in all_regions_same_depth}
        #         for r in all_regions_same_depth:
        #             surr_sum = 0.0
        #             for each_vertex in r.vertexs:
        #                 for d in range(self.dim):
        #                     surr_sum += (each_vertex[d] - point[d]) ** 2
        #             surr_sum_dict[r.region_id] = surr_sum
        #         min_region_id = min(surr_sum_dict, key=surr_sum_dict.get)
        #         return True if min_region_id == self.region_id else False

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

    # def get_depth(self):
    #     depth = 0
    #     p = self.parent
    #     while p:
    #         depth += 1
    #         p = p.parent

    def print_tree(self):
        spaces = " " * self.depth * 8
        prefix = spaces + "|______" if self.parent else ""
        print(prefix + str(self.region_id) + str(self.vertexs))
        if self.children:
            for child in self.children:
                child.print_tree()


def create_sub_region(
    parent_vertexs, parent_region_id, parent_depth, curr_region_id_count
):
    dim = len(parent_vertexs)
    # calculate the centroid
    centroid = []
    for coordinates_one_dim in zip(*parent_vertexs):
        each_dim_centroid = sum(coordinates_one_dim) / dim
        # each_dim_centroid = round(sum(coordinates_one_dim) / dim, 3)
        centroid.append(each_dim_centroid)
    centroid = tuple(centroid)
    # print("------ parent_region_id is: ", parent_region_id, "centriod is: ", centroid)

    # for each sub_region, built it
    region_id_increment_track = 0
    sub_regions = []
    for rest_vertexs in itertools.combinations(enumerate(parent_vertexs), dim - 1):
        vertexs = [()] * dim
        for each_rest_vertex in rest_vertexs:
            vertexs[each_rest_vertex[0]] = each_rest_vertex[1]
        for idx, vertex in enumerate(vertexs):
            if vertex is ():
                vertexs[idx] = centroid
                break
        region_id = curr_region_id_count + region_id_increment_track
        sub_region = Region(
            region_id=region_id, dim=dim, vertexs=vertexs, depth=parent_depth + 1
        )
        region_id_increment_track += 1
        sub_regions.append(sub_region)
    return sub_regions


def build_region_tree(dim, max_depth):
    total_region_list = []

    I = np.identity(dim)
    vertexs = [tuple(vertex) for vertex in I.tolist()]
    root_region = Region(region_id=0, dim=dim, vertexs=vertexs, depth=0)
    total_region_list.append(root_region)
    curr_region_id_count = 1
    for iter_depth in range(1, max_depth, 1):
        parent_depth = iter_depth - 1
        parent_regions = [
            region for region in total_region_list if region.depth == parent_depth
        ]
        for parent_region in parent_regions:
            sub_regions = create_sub_region(
                parent_region.vertexs,
                parent_region.region_id,
                parent_region.depth,
                curr_region_id_count,
            )
            curr_region_id_count += dim
            for sub_region in sub_regions:
                parent_region.add_child(sub_region)
            total_region_list.extend(sub_regions)

    ### not optimal solution
    # total_num = 0
    # for d in range(1, max_depth + 1, 1):
    #     total_num += dim ** (d - 1)
    # total_num = total_num * 801
    # for _ in range(total_num):
    #     one_sample = uniform_sample_from_unit_simplex(size=1, dim=dim)
    #     one_sample_tuple = tuple(one_sample)
    #     total_region_list[0].add_pre_sample_point(one_sample_tuple)
    # # total_region_list[0].dispatch_point_to_children()
    # for region in total_region_list:
    #     # print(region.region_id, len(region.pre_sample_points))
    #     region.dispatch_point_to_children()

    ### optimal but not for c>3
    for region in total_region_list:
        while True:
            one_sample = uniform_sample_from_unit_simplex(size=1, dim=dim)
            one_sample_tuple = tuple(one_sample)
            region.add_pre_sample_point(one_sample_tuple)
            if region.is_pre_sample_enough():
                break  # search check next region

    # root_region.print_tree()
    return total_region_list


if __name__ == "__main__":

    # line = LineString([(1, 0), (0.5, 0.5)])
    # point = Point((0.5, 0.5))
    # print(line.contains(point))

    berth_num = 2
    max_depth = 5  # root region is located at depth-0
    total_region_list = build_region_tree(dim=berth_num, max_depth=max_depth)
    root_region = total_region_list[0]
    root_region.print_tree()

    # min_distance = min(total_region_list, key=attrgetter("distance_to_center"))
    # print(min_distance.region_id)

    # line_flow, line_service, line_rho = get_generated_line_info(
    #     berth_num, 6, 135, "Gaussian", 25, 0
    # )
    # regions_at_max_depth = [
    #     region for region in total_region_list if region.depth == max_depth - 1
    # ]
    # evenest_point = [sum(line_rho.values()) / berth_num] * berth_num
    # evenest_point = [1.0 / berth_num] * berth_num
    # # print(evenest_point)
    # for region in regions_at_max_depth:
    #     is_contain = region.is_point_in_region(evenest_point)
    # print(is_contain, region.vertexs)

    # fig, ax = plt.subplots()
    # samples = total_region_list[1].pre_sample_points
    # x, y, z = zip(*samples)
    # ax.scatter(x, y, c="r")
    # samples = total_region_list[2].pre_sample_points
    # x, y, z = zip(*samples)
    # ax.scatter(x, y, c="g")
    # samples = total_region_list[3].pre_sample_points
    # x, y, z = zip(*samples)
    # ax.scatter(x, y, c="b")
    # fig.savefig("figs/pre_sample_test.jpg")
