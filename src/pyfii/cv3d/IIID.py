from typing import Any, List, Tuple
import cv2
from cv2.typing import MatLike, Scalar
import numpy as np
from .transfer import *
from .typing import Vec3, Degree, Radian


def eye_vector(a: Degree, b: Degree) -> Tuple[float, float, float]:
    return (
        np.cos(np.radians(abs(a))) * np.cos(np.radians(abs(b))),
        np.sin(np.radians(abs(a))) * np.cos(np.radians(abs(b))),
        np.sin(np.radians(abs(b))),
    )


def eye_axis(a: Degree, b: Degree, d0: float) -> Tuple[float, float, float]:
    return (
        -np.cos(np.radians(abs(a))) * np.cos(np.radians(abs(b))) * d0,
        -np.sin(np.radians(abs(a))) * np.cos(np.radians(abs(b))) * d0,
        -np.sin(np.radians(abs(b))) * d0,
    )


def abs_3d_vector(v: Vec3) -> float:
    """取得三维向量的模长

    Args:
        v (Vec3): 三维向量

    Returns:
        float: 三维向量的模长
    """
    assert len(v) == 3
    return np.linalg.norm(v)


def dot_3d_v1_v2(v1: Vec3, v2: Vec3) -> float:
    """两个三维向量的点乘

    Args:
        v1 (Vec3): 三维向量
        v2 (Vec3): 三维向量

    Returns:
        float: 点乘（内积）
    """
    assert len(v1) == 3 and len(v2) == 3
    return np.dot(v1, v2)


def iiid2iid(
    point: Vec3,
    x: float,
    y: float,
    a: Degree,
    b: Degree,
    center: Vec3 = (0, 0, 0),
    d: Vec2 = (1, 0),
) -> Tuple[float, float, float]:
    """三维坐标点投影在二维平面的位置(三维坐标点,二维平面原点xy,观察者面朝角度ab,观察者观察的中心位置)

    Args:
        point (Vec3): 三维坐标点
        x (float): 二维平面原点x
        y (float): 二维平面原点y
        a (Degree): 观察者面朝角度a
        b (Degree): 观察者面朝角度b
        center (Vec3, optional): 观察者观察的中心位置. Defaults to (0, 0, 0).
        d (Vec2, optional): _description_. Defaults to (1, 0).

    Returns:
        Tuple[ float, float, float ]: 第一二个输出为显示的xy坐标,第三个输出为点与观察者的相对距离(用于确定渲染的先后顺序,远先近后)
    """
    a = np.radians(a)
    b = np.radians(b)
    point = rotate3d(
        (point[0] - center[0], point[1] - center[1], point[2] - center[2]), -a, -b
    )
    if d[1] == 0:
        return (
            x - point[1] * d[0],
            y - point[2] * d[0],
            point[0],
        )  # 第一二个输出为显示的xy坐标,第三个输出为点与观察者的相对距离(用于确定渲染的先后顺序,远先近后)
    elif point[0] + d[0] == 0:
        return 0, 0, 0
    else:
        return (
            x - point[1] * d[1] / (point[0] + d[0]),
            y - point[2] * d[1] / (point[0] + d[0]),
            point[0] + d[0],
        )  # 第一二个输出为显示的xy坐标,第三个输出为点与观察者的相对距离(用于确定渲染的先后顺序,远先近后)


def sphere(
    img: MatLike,
    point: Vec3,
    x: float,
    y: float,
    a: Degree,
    b: Degree,
    color: Scalar,
    r: int = 1,
    center: Vec3 = (0, 0, 0),
    thickness: int = -1,
    d: Vec2 = (1, 0),
):
    """在图像上显示球体（点）(img,球心坐标,二维平面原点xy,观察者面朝角度ab,颜色,半径,观察者观察的中心位置)

    Args:
        img (MatLike): 图像
        point (Vec3): 球心坐标
        x (float): 二维平面原点x
        y (float): 二维平面原点y
        a (Degree): 观察者面朝角度a
        b (Degree): 观察者面朝角度b
        color (Scalar): 颜色
        r (int, optional): 半径. Defaults to 1.
        center (Vec3, optional): 观察者观察的中心位置. Defaults to (0, 0, 0).
        thickness (int, optional): 绘制的线宽，默认实心. Defaults to -1.
        d (Vec2, optional): _description_. Defaults to (1, 0).
    """
    x1, y1, z = iiid2iid(point, x, y, a, b, center, d)
    if d[1] == 0:
        cv2.circle(img, (int(x1), int(y1)), int(r+0.5), color, thickness)
    else:
        if z > 0:
            cv2.circle(img, (int(x1), int(y1)), int(r * d[1] / z + 1), color, thickness)


def line(
    img: MatLike,
    point1: Vec3,
    point2: Vec3,
    x: float,
    y: float,
    a: Degree,
    b: Degree,
    color: Scalar,
    thickness: int = 1,
    center: Vec3 = (0, 0, 0),
    line_type: int = cv2.LINE_8,
    d: Vec2 = (1, 0),
):
    """在图像上显示线段(img,端点1坐标,端点2坐标,二维平面原点xy,观察者面朝角度ab,颜色,粗细,观察者观察的中心位置,直线类型)

    Args:
        img (MatLike): 图像
        point1 (Vec3): 端点1坐标
        point2 (Vec3): 端点2坐标
        x (float): 二维平面原点x
        y (float): 二维平面原点y
        a (Degree): 观察者面朝角度a
        b (Degree): 观察者面朝角度b
        color (Scalar): 颜色
        thickness (int, optional): 绘制的线宽，默认实心. Defaults to 1.
        center (Vec3, optional): 观察者观察的中心位置. Defaults to (0, 0, 0).
        line_type (int, optional): 线的类型. Defaults to cv2.LINE_8.
        d (Vec2, optional): _description_. Defaults to (1, 0).
    """
    x1, y1, z1 = iiid2iid(point1, x, y, a, b, center, d)
    x2, y2, z2 = iiid2iid(point2, x, y, a, b, center, d)
    if d[1] == 0:
        cv2.line(
            img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness, line_type
        )
    else:
        if z1 > 0 and z2 > 0:
            cv2.line(
                img, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness, line_type
            )


def ring(
    img: MatLike,
    point: Vec3,
    x: float,
    y: float,
    a: Degree,
    b: Degree,
    color: Scalar,
    r: int,
    center: Vec3 = (0, 0, 0),
    thickness: int = 1,
    d: Vec2 = (1, 0),
    normal_vector: Vec3 = (0, 0, 1),
):
    """在图像上显示圆环

    Args:
        img (MatLike): 图像
        point (Vec3): 圆心坐标
        x (float): 二维平面原点x
        y (float): 二维平面原点y
        a (Degree): 观察者面朝角度a
        b (Degree): 观察者面朝角度b
        color (Scalar): 颜色
        r (int): 半径
        center (Vec3, optional): 观察者观察的中心位置. Defaults to (0, 0, 0).
        thickness (int, optional): 绘制的线宽，默认实心. Defaults to 1.
        d (Vec2, optional): _description_. Defaults to (1, 0).
        normal_vector (Vec3, optional): 圆环平面的法向量. Defaults to (0, 0, 1).
    """
    normal = np.asarray(normal_vector, dtype=float)
    normal_length = np.linalg.norm(normal)
    if not np.isfinite(normal_length) or normal_length == 0:
        raise ValueError("normal_vector must be a finite, non-zero 3D vector")
    normal /= normal_length

    # Build an orthonormal basis in the ring plane.  Projecting the real 3D
    # circumference fixes both the missing ellipse rotation and the invalid
    # constant-depth approximation used by the old perspective path.
    reference = np.array((0.0, 0.0, 1.0))
    if abs(normal[2]) > 0.9:
        reference = np.array((1.0, 0.0, 0.0))
    axis_u = np.cross(normal, reference)
    axis_u /= np.linalg.norm(axis_u)
    axis_v = np.cross(normal, axis_u)
    origin = np.asarray(point, dtype=float)

    angles = np.linspace(0, 2 * np.pi, 49)[:-1]
    points3d = origin + r * (
        np.cos(angles)[:, None] * axis_u + np.sin(angles)[:, None] * axis_v
    )
    relative = points3d - np.asarray(center, dtype=float)
    angle_a = np.radians(a)
    angle_b = np.radians(b)
    cos_a, sin_a = np.cos(angle_a), np.sin(angle_a)
    cos_b, sin_b = np.cos(angle_b), np.sin(angle_b)
    camera_x1 = relative[:, 0] * cos_a + relative[:, 1] * sin_a
    camera_y = relative[:, 1] * cos_a - relative[:, 0] * sin_a
    camera_x = camera_x1 * cos_b + relative[:, 2] * sin_b
    camera_z = relative[:, 2] * cos_b - camera_x1 * sin_b
    if d[1] == 0:
        projected_float = np.column_stack((x-camera_y*d[0], y-camera_z*d[0]))
        visible = np.ones(len(points3d), dtype=bool)
    else:
        depth = camera_x + d[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            projected_float = np.column_stack(
                (x-camera_y*d[1]/depth, y-camera_z*d[1]/depth)
            )
        visible = depth > 1e-6
    visible &= np.isfinite(projected_float).all(axis=1)
    visible &= (np.abs(projected_float) < 2**30).all(axis=1)
    projected_float[~visible] = 0
    projected = np.rint(projected_float).astype(np.int64)

    # Draw segment-by-segment so a ring crossing the perspective camera plane
    # does not produce coordinates at infinity or connect hidden points.
    if thickness < 0 and all(visible):
        cv2.fillPoly(img, [projected.astype(np.int32)], color, cv2.LINE_AA)
        return
    if all(visible):
        cv2.polylines(
            img, [projected.astype(np.int32)], True, color, max(1, thickness), cv2.LINE_AA
        )
        return
    segments = []
    for index in range(len(projected)):
        next_index = (index + 1) % len(projected)
        if visible[index] and visible[next_index]:
            segments.append(projected[[index, next_index]].astype(np.int32))
    if segments:
        cv2.polylines(img, segments, False, color, max(1, thickness), cv2.LINE_AA)


def distance(
    obj3d: List[Any],
    x: float,
    y: float,
    A: Degree,
    B: Degree,
    center: Vec3 = (0, 0, 0),
    d: Vec2 = (1, 0),
) -> float:
    """计算距离

    Args:
        obj3d (List[Any]): 三维物体
        x (float): 二维平面原点x
        y (float): 二维平面原点y
        A (Degree): 观察者面朝角度a
        B (Degree): 观察者面朝角度b
        center (Vec3, optional): 观察者观察的中心位置. Defaults to (0, 0, 0).
        d (Vec2, optional): _description_. Defaults to (1, 0).

    Returns:
        float: 距离
    """
    if obj3d[-1] == "text":
        return -10000
    elif obj3d[-1] == "line":
        return iiid2iid(
            (
                (obj3d[0][0] + obj3d[1][0]) / 2,
                (obj3d[0][1] + obj3d[1][1]) / 2,
                (obj3d[0][2] + obj3d[1][2]) / 2,
            ),
            x,
            y,
            A,
            B,
            center,
            d,
        )[2]
    elif obj3d[-1] == "sphere":
        return iiid2iid(obj3d[0], x, y, A, B, center, d)[2]
    elif obj3d[-1] == "ring":
        return iiid2iid(obj3d[0], x, y, A, B, center, d)[2]


def show(
    obj3d_list, center=(0, 0, 0), x=720, y=720, imshow=[-1], d=(1, 0)
):  # 显示(aixs：记录所有需要显示的点线面的列表,观察者观察的中心位置,显示的视图大小,imshow：A,B角度，k,l转动参数，最后一个模式设置（-1为直接展示，0为暂停，1为导出图片),d：(1,0)为正交，比例为1，(200,100)表示观察者距离中心200，距观察者100处比例为1)
    if imshow[-1] == 0:
        A = imshow[0]
        B = imshow[1]
        k = imshow[2]
        l = imshow[3]
    elif imshow[-1] == 1:
        A = imshow[0]
        B = imshow[1]
        k = 1
        l = 0
    else:
        A = 90
        B = 0
        k = 1
        l = 0
    obj3d_list = sorted(
        obj3d_list,
        key=lambda obj3d: distance(obj3d, x, y, A, B, center, d),
        reverse=True,
    )  # 计算渲染顺序
    while True:
        img = np.zeros((y, x, 3), np.uint8)
        for obj3d in obj3d_list:
            if obj3d[-1] == "sphere":
                sphere(
                    img,
                    obj3d[0],
                    x / 2,
                    y / 2,
                    A,
                    B,
                    obj3d[1],
                    obj3d[2],
                    center,
                    obj3d[3],
                    d,
                )
            elif obj3d[-1] == "line":
                line(
                    img,
                    obj3d[0],
                    obj3d[1],
                    x / 2,
                    y / 2,
                    A,
                    B,
                    obj3d[2],
                    obj3d[3],
                    center,
                    obj3d[4],
                    d,
                )
            elif obj3d[-1] == "ring":
                if len(obj3d) == 5:
                    ring(
                        img,
                        obj3d[0],
                        x / 2,
                        y / 2,
                        A,
                        B,
                        obj3d[1],
                        obj3d[2],
                        center,
                        obj3d[3],
                        d,
                    )
                elif len(obj3d) == 6:
                    ring(
                        img,
                        obj3d[0],
                        x / 2,
                        y / 2,
                        A,
                        B,
                        obj3d[1],
                        obj3d[2],
                        center,
                        obj3d[3],
                        d,
                        obj3d[4],
                    )
            elif obj3d[-1] == "text":
                cv2.putText(
                    img,
                    obj3d[0],
                    obj3d[1],
                    cv2.FONT_HERSHEY_SIMPLEX,
                    obj3d[2],
                    obj3d[3],
                    obj3d[4],
                )
        A = (A + 180) % 360 - 180
        cv2.putText(
            img, str(A), (0, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )
        cv2.putText(
            img, str(B), (0, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )
        if imshow[-1] == 0:
            break
        cv2.imshow("img", img)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # esc键退出
            break
        elif key == ord("d"):  # w,a,s,d,左右上下旋转
            A += k
            A = (A + 180) % 360 - 180
            k += 1
            l = 0
        elif key == ord("a"):
            A -= k
            A = (A + 180) % 360 - 180
            k += 1
            l = 0
        elif key == ord("w"):
            B -= k
            if B < -90:
                B = -90
            k += 1
            l = 0
        elif key == ord("s"):
            B += k
            if B > 90:
                B = 90
            k += 1
            l = 0
        else:
            l += 1
            # print(l)
            if l > 49:
                k = 1
                l = 0
    if imshow[-1] == 0:
        return img
    elif imshow[-1] == 1:
        return A, B
    else:
        cv2.destroyAllWindows()
