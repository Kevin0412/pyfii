1. 6m毯

2. 4m毯

    1. 导入
        ```python
        import pyfii as pf
        ```

    2. 新建无人机
        ```python
        d1=pf.Drone(0,0,pf.drone_config_4m)
        d2=pf.Drone(0,0,pf.drone_config_4m)
        d3=pf.Drone(0,0,pf.drone_config_4m)

        ds=[d1,d2,d3]
        ```

    3. 动作
        ```python
        for d,y in zip(ds,range(60,360,120)):
            d.X=20
            d.Y=y

            d.takeoff(1,80)

            d.inittime(4)
            d.VelXY(200,400)
            d.VelZ(200,400)
            d.move2(340,y,250)
            d.TurnOnAll('#ffff00')
            d.delay(500)
            d.TurnOnAll((0,255,0))
            d.delay(1312)
            d.TurnOnAll([
                '#ffff00','#ffff00','#ffff00','#ffff00',
                '#ffff00','#ffff00','#ffff00','#ffff00',
                '#ffff00','#ffff00','#ffff00','#ffff00'
            ])
            d.delay(500)
            d.TurnOnAll([
                (255,0,0),(255,0,0),(255,0,0),(255,0,0),
                (255,0,0),(255,0,0),(255,0,0),(255,0,0),
                (255,0,0),(255,0,0),(255,0,0),(255,0,0)
            ])

            d.inittime(7)
            d.BlinkFastAll(['#ff0000',(255,255,0),'#00ff00'])
            '''
            相当于
            d.BlinkFastAll([
                '#ff0000',(255,255,0),'#00ff00',
                '#ff0000',(255,255,0),'#00ff00',
                '#ff0000',(255,255,0),'#00ff00',
                '#ff0000',(255,255,0),'#00ff00'
            ])
            '''
            d.land()

            d.end()
        ```