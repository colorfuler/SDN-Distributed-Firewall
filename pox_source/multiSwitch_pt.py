"""
L2 Learning Multiple Switch Prototype
by Justin Gregory V. Pena

This prototype is similar to the switch implementation
except that it stores the multiple switch connections into a list
allowing the user to interactively controll each switch
in a multiple switch topology.
"""
from pox.core import core
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.util import dpidToStr
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt

log = core.getLogger()
#The following maps are used by the packet parser
opcode_map = {1:'REQUEST', 2:'REPLY', 3:'REV_REQUEST', 4:'REV_REPLY'}
ipv4_protocols = {4:'IPv4', 1:'ICMP_PROTOCOL', 6:'TCP_PROTOCOL', 17:'UDP_PROTOCOL', 2:'IGMP_PROTOCOL'}  #IPv4 协议

#store available switch connections here  存储交换机的信息
switch = list()  #列出交换机的信息

class Switch (object):   #交换机类

  def __init__ (self, connection):
    # Keep track of the connection to the switch so that we can  追踪交换机的连接以便于我们收集交换机的信息
    # send it messages!
    self.connection = connection  #将连接信息赋值

    # This binds our PacketIn event listener   #绑定事件监听器
    connection.addListeners(self)

    # Use this table to keep track of which ethernet address is on  交换机的追踪
    # which switch port (keys are MACs, values are ports).  哪个交换机的端口键是Mac地址，值是端口
    self.mac_to_port = {}  

    log.info("Switch Active")  #日志信息交换机处于活跃状态

  def resend_packet (self, packet_in, out_port):  #显示交换机的packet in数据包 和输出端口
    """
    Instructs the switch to resend a packet that it had sent to us.
    "packet_in" is the ofp_packet_in object the switch had sent to the
    controller due to a table-miss.
    """
    
    msg = of.ofp_packet_out()
    msg.data = packet_in

    # Add an action to send to the specified port 添加动作到指定端口
    action = of.ofp_action_output(port = out_port)
    msg.actions.append(action)

    # Send message to switch
    self.connection.send(msg)

  def switchImplementation (self, packet, packet_in):
    """
    Implement switch-like behavior. 类似于交换的行为
    """

    #Parse packet info to gain an idea of what is happening 解析数据包以了解发生的情况
    #if controller receives packet  控制器接收到数据包执行以下行为
    if packet.type == pkt.ethernet.IP_TYPE:
      ip_packet = packet.payload
      log.info("IP Packet detected")
      log.info("IP protocol: %s" % (ipv4_protocols[ip_packet.protocol]))
      log.info("Source IP: %s" % (ip_packet.srcip))
      log.info("Destination IP: %s" % (ip_packet.dstip))

    if packet.type == pkt.ethernet.ARP_TYPE:
      arp_packet = packet.payload
      log.info("ARP Packet detected")
      log.info("ARP opcode: %s" % (opcode_map[arp_packet.opcode]))
      log.info("Source MAC: %s" % (arp_packet.hwsrc))
      log.info("Destination MAC: %s" % (arp_packet.hwdst))

    # Learn the port for the source MAC
    self.mac_to_port[packet.src] = packet_in.in_port
    src_port = packet_in.in_port

    if packet.dst in self.mac_to_port:
        dst_port = self.mac_to_port[packet.dst]

        log.debug("Installing %s.%i -> %s.%i" % 
                  (packet.src, src_port, packet.dst, dst_port))
        msg = of.ofp_flow_mod()   #pox组件对交换机上的流表进行修改流表项的内容包括指定的匹配域,以及为流表所指定的动作 actions。actions 中包括了 output、drop、set_vlan_vi等等。
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = 10#流表在交换机中的超时时间，当这个流表被匹配到之后，流表时间会刷新，重新开始记时。如果不指定，默认没有超时时间
        msg.hard_timeout = 30#同样是流表在交换机中的超时时间，与 idle_timeout 字段不同的是，流表时间不会被刷新，也就是到了指定的时间流表一定会被删除
        msg.actions.append(of.ofp_action_output(port = dst_port))#actions – 为流表指定的一系列动作
        self.connection.send(msg)
        self.resend_packet(packet_in, dst_port)
    else:
      # Flood the packet out everything but the input port 洪泛
      # This part looks familiar, right?
      self.resend_packet(packet_in, of.OFPP_ALL)

  def _handle_PacketIn (self, event):
    """
    Handles packet in messages from the switch.  处理来自交换机的数据包
    """

    packet = event.parsed # This is the parsed packet data.
    if not packet.parsed:
      log.warning("Ignoring incomplete packet")
      return

    packet_in = event.ofp # The actual ofp_packet_in message.

    self.switchImplementation(packet, packet_in)

  #Used to construct and send an IP packet  用于构造和发送ip数据包
  #This is primarily used as a secondary test option aside from ping  除了ping以外,用于辅助测试选项
  #Could also have applications for multi-switch topology testing  有用于多交换机检测的应用程序
  def send_IP_packet(self, src_ip, dst_ip):
    ip4_Packet = pkt.ipv4()
    ip4_Packet.srcip = IPAddr(src_ip)
    ip4_Packet.dstip = IPAddr(dst_ip)
    ether = pkt.ethernet()
    ether.type = pkt.ethernet.IP_TYPE
    ether.srcip = IPAddr(src_ip)
    ether.dstip = IPAddr(dst_ip)
    ether.payload = ip4_Packet
    msg = of.ofp_packet_out()
    msg.data = ether
    msg.actions.append(of.ofp_action_output(port = of.OFPP_ALL))
    self.connection.send(msg)

  def returnDPID(self):
    dpid = dpidToStr(self.connection.dpid)
    log.debug("DPID: %s" % (dpid))

def launch ():
  """
  Starts the component
  """
  def start_switch (event):
    log.debug("Controlling %s" % (event.connection,))
    switches.append(Switch(event.connection))
    core.Interactive.variables['switches'] = switches
  core.openflow.addListenerByName("ConnectionUp", start_switch)
