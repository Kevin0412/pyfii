class A:
    def __init__(self, x):
        self.x = x

    def f(self, x):
        self.x = x
        print(self.x)

    def g(x):
        print(x)

def cl(f, p):
    f(**p)

def test():
    a = A(1)
    cl(a.f, {'x':2})
    cl(A.f, {'self':a, 'x':3})
    # cl(a.g, {'x':4}) error
    cl(A.g, {'x':5})
    # cl(A.g, [6]) error
    print('-------')
    def f():
        print('f1')
    l = [[f,dict()]]
    def f():
        print('f2')
    l.append([f,dict()])
    for (f,p) in l:
        cl(f,p)


test()