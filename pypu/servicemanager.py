import service_flickr
import service_facebook
import service_wp

class servicemanager:

    def __init__(self):
        self.services=[]
        self.services.append(service_flickr.service_flickr())
        self.services.append(service_wp.service_wp())
        self.services.append(service_facebook.service_facebook())

    def GetServices(self,filename):
        """Returns a list of service objects handling this file type"""
        objlist=[]
        for sobj in self.services:
            if sobj.KnowsFile(filename) :
                objlist.append(sobj)

        if len(objlist)==0:
            return None

        return objlist

    def GetServiceObj(self,servicename):
        """Given a service name string, returns
        the object that corresponds to the service"""
        for sobj in self.services:
            if sobj.GetName().lower()==servicename.lower():
                return sobj

        return None

    def PrintServices(self):
        for sobj in self.services:
            print sobj.GetName()
